"""Project-scoped command handlers over the canonical persisted state document."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from symbox.cli.now_parser import parse_now_tokens
from symbox.domain.models import SVK, DomainInvariantError, ObjectCategory
from symbox.domain.svk_identity import identify_svk
from symbox.integrations.python_bindings import ProjectPythonBindingLoader
from symbox.persistence.backup_repository import GitBackupRepository
from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope, StateRepository


class CommandRuntime:
    """Execute one CLI request against a single isolated project scope."""

    def __init__(self, root: Path) -> None:
        self.scope = ProjectScope(root)
        self.states = StateRepository(self.scope)
        self.backups = GitBackupRepository(self.scope)
        self.loader = ProjectPythonBindingLoader()

    def create(self, name: str, category: str) -> dict[str, Any]:
        state = self.states.load()
        normalized = name.strip()
        if any(record.get("name") == normalized for record in state.objects):
            raise DomainInvariantError(f"object already exists: {normalized}")
        selected = ObjectCategory(category)
        objects = (*state.objects, {"name": normalized, "category": selected.value})
        self._save(replace(state, objects=objects))
        return {"name": normalized, "category": selected.value}

    def delete(self, name: str) -> dict[str, Any]:
        state = self.states.load()
        self._require_object(state, name)
        objects = tuple(record for record in state.objects if record.get("name") != name)
        bindings = tuple(record for record in state.bindings if record.get("object_name") != name)
        adj_facts = tuple(record for record in state.adj_facts if record.get("subject") != name)
        tag_facts = tuple(record for record in state.tag_facts if record.get("subject") != name)
        relations = tuple(
            record
            for record in state.relations
            if name not in {record.get("subject"), record.get("verb")}
        )
        self._save(
            replace(
                state,
                objects=objects,
                bindings=bindings,
                adj_facts=adj_facts,
                tag_facts=tag_facts,
                relations=relations,
            )
        )
        return {"name": name, "deleted": True}

    def bind(
        self,
        name: str,
        source_path: str,
        qualified_name: str,
        *,
        is_verb: bool,
    ) -> dict[str, Any]:
        state = self.states.load()
        self._require_object(state, name)
        loaded = self.loader.load(
            self.scope.root,
            source_path,
            qualified_name,
            is_verb=is_verb,
        )
        reference = loaded.reference
        records = [record for record in state.bindings if record.get("object_name") != name]
        records.append(
            {
                "object_name": name,
                "source_path": reference.source_path,
                "qualified_name": reference.qualified_name,
                "source_digest": reference.source_digest,
                "is_verb": reference.is_verb,
            }
        )
        self._save(replace(state, bindings=tuple(records)))
        return records[-1]

    def unbind(self, name: str) -> dict[str, Any]:
        state = self.states.load()
        if not any(record.get("object_name") == name for record in state.bindings):
            raise DomainInvariantError(f"object has no binding: {name}")
        bindings = tuple(record for record in state.bindings if record.get("object_name") != name)
        self._save(replace(state, bindings=bindings))
        return {"name": name, "unbound": True}

    def set_attributes(self, name: str, assignments: tuple[str, ...]) -> dict[str, Any]:
        state = self.states.load()
        self._require_object(state, name)
        from symbox.application.attributes import parse_assignments

        values = parse_assignments(assignments)
        records = {(record.get("subject"), record.get("key")): record for record in state.adj_facts}
        for key, value in values.items():
            records[name, key] = {
                "subject": name,
                "key": key,
                "value": value,
                "sources": [{"kind": "explicit", "source_id": f"cli:{name}:{key}"}],
            }
        self._save(replace(state, adj_facts=tuple(records.values())))
        return {"subject": name, "values": values}

    def unset_attributes(self, name: str, keys: tuple[str, ...]) -> dict[str, Any]:
        state = self.states.load()
        self._require_object(state, name)
        normalized = tuple(key.strip() for key in keys)
        existing = {(record.get("subject"), record.get("key")) for record in state.adj_facts}
        missing = tuple(key for key in normalized if (name, key) not in existing)
        if not normalized or missing:
            raise DomainInvariantError(f"unknown attributes: {missing}")
        adj_facts = tuple(
            record
            for record in state.adj_facts
            if (record.get("subject"), record.get("key")) not in {(name, key) for key in normalized}
        )
        self._save(replace(state, adj_facts=adj_facts))
        return {"subject": name, "keys": normalized}

    def now(self, tokens: tuple[str, ...]) -> dict[str, Any]:
        state = self.states.load()
        parsed = parse_now_tokens(tokens)
        self._require_object(state, parsed.subject)
        self._require_object(state, parsed.verb)
        binding = next(
            (
                record
                for record in state.bindings
                if record.get("object_name") == parsed.verb and record.get("is_verb") is True
            ),
            None,
        )
        if binding is None:
            raise DomainInvariantError(f"object is not a bound verb: {parsed.verb}")
        loaded = self.loader.load(
            self.scope.root,
            str(binding["source_path"]),
            str(binding["qualified_name"]),
            is_verb=True,
        )
        if loaded.reference.source_digest != binding["source_digest"]:
            raise DomainInvariantError(f"binding source changed for object: {parsed.verb}")
        from symbox.application.signature_binding import bind_effective_arguments

        effective = bind_effective_arguments(
            loaded.signature,
            parsed.subject,
            parsed.args,
            parsed.kwargs,
        )
        accepted = loaded.callable(
            effective.subject,
            *effective.args,
            **dict(effective.kwargs),
        )
        if accepted is not True:
            raise DomainInvariantError(f"verb check rejected relation: {parsed.verb}")
        relation = SVK(parsed.subject, parsed.verb, effective.args, effective.kwargs)
        node_key = identify_svk(relation).key.encode()
        records = [record for record in state.relations if record.get("node_key") != node_key]
        records.append(
            {
                "node_key": node_key,
                "subject": relation.subject,
                "verb": relation.verb,
                "args": relation.args,
                "kwargs": dict(relation.kwargs),
            }
        )
        self._save(replace(state, relations=tuple(records)))
        return {"node_key": node_key, "subject": parsed.subject, "verb": parsed.verb}

    def list(self, target: str) -> Any:
        state = self.states.load()
        if target == "objects":
            verbs = {
                record["object_name"] for record in state.bindings if record.get("is_verb") is True
            }
            return tuple(
                {
                    "name": record["name"],
                    "category": record["category"],
                    "is_verb": record["name"] in verbs,
                }
                for record in state.objects
            )
        if target == "verbs":
            return tuple(record for record in state.bindings if record.get("is_verb") is True)
        if target == "backups":
            return tuple(
                {
                    "commit_id": record.commit_id,
                    "note": record.note,
                    "created_at": record.created_at.isoformat(),
                }
                for record in self.backups.list_backups()
            )
        self._require_object(state, target)
        return {
            "object": next(record for record in state.objects if record.get("name") == target),
            "binding": next(
                (record for record in state.bindings if record.get("object_name") == target),
                None,
            ),
            "attributes": tuple(
                record for record in state.adj_facts if record.get("subject") == target
            ),
            "tags": tuple(record for record in state.tag_facts if record.get("subject") == target),
            "relations": tuple(
                record
                for record in state.relations
                if target in {record.get("subject"), record.get("verb")}
            ),
        }

    def backup_create(self, note: str) -> dict[str, Any]:
        record = self.backups.create(self.states.load(), note)
        return {
            "commit_id": record.commit_id,
            "note": record.note,
            "created_at": record.created_at.isoformat(),
        }

    def backup_list(self) -> Any:
        return self.list("backups")

    def backup_delete(self, commit_ids: tuple[str, ...]) -> dict[str, Any]:
        self.backups.delete(commit_ids)
        return {"deleted": commit_ids}

    def backup_rollback(self, commit_id: str) -> dict[str, Any]:
        state = self.backups.rollback(commit_id, self.states)
        return {"commit_id": commit_id, "revision": state.revision}

    def _save(self, state: StateDocument) -> None:
        self.states.save(replace(state, revision=state.revision + 1))

    @staticmethod
    def _require_object(state: StateDocument, name: str) -> None:
        if not any(record.get("name") == name for record in state.objects):
            raise DomainInvariantError(f"unknown object: {name}")
