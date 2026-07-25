from typing import Any, Dict, List, Optional, Tuple
from symbox.core.adj import Adj
from symbox.core.backup import BackupManager
from symbox.core.dynamic_bind import load_func_from_file
from symbox.core.embedding import EmbeddingDetector
from symbox.core.ltms_wrapper import ContradictionError, LTMSWrapper
from symbox.core.meta import Attention, Worry
from symbox.core.storage import StorageManager
from symbox.core.subject import Subject
from symbox.core.verb import Verb


class SymboxEngine:
    """Central reasoning engine coordinating objects, LTMS, embedding detection, and backups."""

    def __init__(self, sbox_dir: str = "./.sbox"):
        self.sbox_dir = sbox_dir
        self.subjects: Dict[str, Subject] = {}
        self.verbs: Dict[str, Verb] = {}
        self.svo_triples: List[Dict[str, str]] = []

        self.ltms = LTMSWrapper(title="symbox_main")
        self.embedding = EmbeddingDetector()
        self.backup = BackupManager(sbox_dir=sbox_dir)
        self.storage = StorageManager(state_file=f"{sbox_dir}/state.json")

        # Load persisted state if exists
        self.load_state()

    def create_subject(self, name: str, kind: str = "physical") -> Subject:
        if name in self.subjects:
            return self.subjects[name]

        if kind == "meta":
            obj = Subject(name=name, kind="meta")
        else:
            obj = Subject(name=name, kind=kind)

        self.subjects[name] = obj
        self.ltms.get_or_create_node(f"Subject:{name}", is_assumption=True)
        self.ltms.set_node_truth(f"Subject:{name}", is_true=True)
        self.save_state()
        return obj

    def delete_subject(self, name: str) -> bool:
        if name not in self.subjects:
            return False

        # Retract subject in LTMS
        self.ltms.retract_node(f"Subject:{name}")
        # Retract associated SVO triples
        remaining_svo = []
        for svo in self.svo_triples:
            if svo["s"] == name or svo["o"] == name or svo["v"] == name:
                key = f"SVO:{svo['s']}:{svo['v']}:{svo['o']}"
                self.ltms.retract_node(key)
            else:
                remaining_svo.append(svo)
        self.svo_triples = remaining_svo

        del self.subjects[name]
        self.save_state()
        return True

    def create_verb(self, name: str) -> Verb:
        if name in self.verbs:
            return self.verbs[name]
        v = Verb(name=name)
        self.verbs[name] = v
        self.save_state()
        return v

    def bind_function(
        self, target_name: str, func_name: str, file_path: str, is_verb: bool = False
    ) -> Any:
        func_or_class = load_func_from_file(file_path, func_name)

        if is_verb:
            # Bind to Verb
            v = self.create_verb(target_name)
            v.check_func = func_or_class
            v.func_name = func_name
            v.module_path = file_path
        else:
            # Bind to Subject or instantiate Worry
            if isinstance(func_or_class, type) and issubclass(func_or_class, Worry):
                worry_obj = func_or_class(
                    name=target_name,
                    watch_subject_name=target_name,
                    func_name=func_name,
                    module_path=file_path,
                )
                worry_obj.engine_callback = self._on_worry_triggered
                self.subjects[target_name] = worry_obj
            else:
                # Subject attribute check / function
                if target_name not in self.subjects:
                    self.create_subject(target_name)
                obj = self.subjects[target_name]
                if isinstance(obj, Worry):
                    obj.condition_func = func_or_class
                    obj.func_name = func_name
                    obj.module_path = file_path
                    obj.engine_callback = self._on_worry_triggered

        self.save_state()
        return func_or_class

    def unbind_function(self, target_name: str, func_name: str, is_verb: bool = False) -> bool:
        if is_verb and target_name in self.verbs:
            self.verbs[target_name].check_func = None
            self.verbs[target_name].func_name = None
            self.verbs[target_name].module_path = None
            self.save_state()
            return True
        elif target_name in self.subjects:
            obj = self.subjects[target_name]
            if isinstance(obj, Worry):
                obj.condition_func = None
                obj.func_name = None
                obj.module_path = None
                self.save_state()
                return True
        return False

    def _on_worry_triggered(self, worry: Worry, triggered: bool) -> None:
        """Observer callback when Worry condition triggers."""
        worry_node_key = f"Worry:{worry.name}"
        self.ltms.set_node_truth(worry_node_key, is_true=triggered, force=True)

    def set_attributes(
        self, obj_name: str, kv_pairs: Dict[str, Any], force: bool = False
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Set attributes/adj keys on object with embedding threshold check."""
        if obj_name not in self.subjects:
            self.create_subject(obj_name)

        subj = self.subjects[obj_name]

        # Check embedding similarity threshold for new keys against existing Adj keys
        existing_adj_keys = list(subj.adj.keys())
        for k, v in kv_pairs.items():
            if k not in existing_adj_keys and not force:
                needs_conf, conf_dict = self.embedding.check_threshold(
                    target_obj=obj_name, proposed_key=k, existing_keys=existing_adj_keys
                )
                if needs_conf:
                    return False, conf_dict

        # Apply attribute updates & Adj patches
        for k, v in kv_pairs.items():
            if isinstance(v, bool) or isinstance(v, dict):
                # Treated as Adj patch if key looks like Adjective or explicit boolean/dict
                adj_obj = Adj(name=k, value=v)
                subj.set_adj(adj_obj)
                self.ltms.set_node_truth(f"Adj:{obj_name}:{k}", is_true=bool(v), force=force)
            subj.set_attribute(k, v)

        # Post-update Worry observer check
        self.evaluate_all_worries()
        self.save_state()
        return True, None

    def unset_attributes(self, obj_name: str, keys: List[str]) -> bool:
        if obj_name not in self.subjects:
            return False
        subj = self.subjects[obj_name]
        for k in keys:
            subj.unset_attribute(k)
            subj.unset_adj(k)
            self.ltms.retract_node(f"Adj:{obj_name}:{k}")
        self.evaluate_all_worries()
        self.save_state()
        return True

    def assert_svo(
        self, s_name: str, v_name: str, o_name: str, if_force: bool = False
    ) -> Tuple[bool, str]:
        """Assert an S V O ground relation with LTMS truth propagation and constraint checking."""
        if s_name not in self.subjects:
            self.create_subject(s_name)
        if o_name not in self.subjects:
            self.create_subject(o_name)
        if v_name not in self.verbs:
            self.create_verb(v_name)

        subj = self.subjects[s_name]
        obj = self.subjects[o_name]
        verb = self.verbs[v_name]

        # 1. Kind domain/range validation
        valid_kind, err_msg = verb.validate_kinds(subj.kind, obj.kind)
        if not valid_kind:
            if not if_force:
                return False, f"Kind validation failed: {err_msg}"

        # 2. Logic check function evaluation
        logic_passed = verb.check(subj.attributes, obj.attributes)
        if not logic_passed:
            if not if_force:
                return False, f"Verb logic rule '{v_name}.check({s_name}, {o_name})' evaluated to False"

        # 3. Veto rules check (e.g. Rotten vetoes Eats)
        svo_key = f"SVO:{s_name}:{v_name}:{o_name}"
        for veto_adj in verb.veto_rules:
            if veto_adj in subj.adj and subj.adj[veto_adj].value:
                adj_key = f"Adj:{s_name}:{veto_adj}"
                self.ltms.add_veto_clause(adj_key, svo_key)
            if veto_adj in obj.adj and obj.adj[veto_adj].value:
                adj_key = f"Adj:{o_name}:{veto_adj}"
                self.ltms.add_veto_clause(adj_key, svo_key)

        # 4. Worry node check (e.g. LowBattery forbids Operates)
        for w_name, w_obj in self.subjects.items():
            if isinstance(w_obj, Worry) and w_obj.is_active:
                worry_key = f"Worry:{w_name}"
                self.ltms.add_veto_clause(worry_key, svo_key)

        # 5. LTMS assertion & truth propagation
        try:
            self.ltms.assert_svo(svo_key, if_force=if_force)
        except ContradictionError as e:
            return False, f"LTMS Contradiction on SVO assertion ({s_name} {v_name} {o_name}): {e}"

        # Success - add to SVO triples
        svo_item = {"s": s_name, "v": v_name, "o": o_name}
        if svo_item not in self.svo_triples:
            self.svo_triples.append(svo_item)

        # Evaluate worry post-propagation fallback sweep
        self.evaluate_all_worries()
        self.save_state()
        return True, "SVO assertion successfully committed to graph."

    def evaluate_all_worries(self) -> None:
        """Post-propagation sweep over all registered Worry nodes (Section 4.4 Choice B)."""
        for s_name, subj in list(self.subjects.items()):
            if isinstance(subj, Worry):
                watch_target = self.subjects.get(subj.watch_subject_name) if subj.watch_subject_name else None
                if watch_target:
                    subj.evaluate_and_trigger(watch_target)

    def list_summary(self, target: str = "objects") -> Any:
        if target == "objects":
            return [subj.to_dict() for subj in self.subjects.values() if not isinstance(subj, (Worry, Attention))]
        elif target == "verbs":
            return [verb.to_dict() for verb in self.verbs.values()]
        elif target == "worries":
            return [subj.to_dict() for subj in self.subjects.values() if isinstance(subj, Worry)]
        elif target == "backups":
            return self.backup.log()
        elif target in self.subjects:
            return self.subjects[target].to_dict()
        elif target in self.verbs:
            return self.verbs[target].to_dict()
        else:
            return {"error": f"Target '{target}' not found."}

    def save_state(self) -> None:
        data = {
            "subjects": {k: v.to_dict() for k, v in self.subjects.items()},
            "verbs": {k: v.to_dict() for k, v in self.verbs.items()},
            "svo": self.svo_triples,
        }
        self.storage.save(data)

    def load_state(self) -> None:
        data = self.storage.load()

        self.subjects.clear()
        for k, v in data.get("subjects", {}).items():
            kind = v.get("kind", "physical")
            if kind == "meta" and "watch_subject_name" in v:
                self.subjects[k] = Worry.from_dict(v)
                self.subjects[k].engine_callback = self._on_worry_triggered
            elif kind == "meta" and k == "main_attention":
                self.subjects[k] = Attention(name=k, attributes=v.get("attributes", {}))
            else:
                self.subjects[k] = Subject.from_dict(v)
            
            # Re-register LTMS nodes
            self.ltms.get_or_create_node(f"Subject:{k}", is_assumption=True)

        self.verbs.clear()
        for k, v in data.get("verbs", {}).items():
            self.verbs[k] = Verb.from_dict(v)

        self.svo_triples = data.get("svo", [])
        for svo in self.svo_triples:
            key = f"SVO:{svo['s']}:{svo['v']}:{svo['o']}"
            self.ltms.get_or_create_node(key, is_assumption=True)
