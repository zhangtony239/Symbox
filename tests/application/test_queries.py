"""Deterministic and read-only state query tests."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from symbox.application.attributes import AttributeState, set_attributes
from symbox.application.bindings import BindingEntry, BindingState
from symbox.application.objects import ObjectNotFoundError, ObjectState, create_object
from symbox.application.queries import (
    QueryState,
    get_object_detail,
    list_objects,
    list_verbs,
)
from symbox.application.relations import RelationFact
from symbox.application.tags import add_explicit_tag, sync_adj_tags
from symbox.domain.models import SVK, BindingRef, ObjectCategory
from symbox.domain.node_keys import NodeKey
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import Assumption, Justification, Premise, TruthNode, TruthValue
from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope, StateRepository


def _objects() -> BindingState:
    state = ObjectState((), InMemoryTruthKernel())
    state = create_object(state, "zeta", ObjectCategory.PHYSICAL)
    state = create_object(state, "alpha", ObjectCategory.ABSTRACT)
    state = create_object(state, "monitor", ObjectCategory.META)
    reference = BindingRef("rules/checks.py", "check", "a" * 64, is_verb=True)
    return BindingState(state, (BindingEntry("zeta", reference),))


def test_list_objects_returns_name_sorted_classification_and_verb_marker() -> None:
    summaries = list_objects(QueryState(_objects()))

    assert tuple(asdict(summary) for summary in summaries) == (
        {"name": "alpha", "category": ObjectCategory.ABSTRACT, "is_verb": False},
        {"name": "monitor", "category": ObjectCategory.META, "is_verb": False},
        {"name": "zeta", "category": ObjectCategory.PHYSICAL, "is_verb": True},
    )


def test_list_objects_returns_empty_success_collection() -> None:
    empty = BindingState(ObjectState((), InMemoryTruthKernel()))

    assert list_objects(QueryState(empty)) == ()


def test_list_verbs_filters_plain_bindings_and_returns_safe_summary() -> None:
    objects = _objects()
    plain = BindingRef("rules/plain.py", "check", "b" * 64)
    state = BindingState(
        objects.objects,
        tuple(
            sorted(
                (*objects.bindings, BindingEntry("alpha", plain)),
                key=lambda item: item.object_name,
            )
        ),
    )

    summaries = list_verbs(QueryState(state))

    assert tuple(asdict(summary) for summary in summaries) == (
        {
            "name": "zeta",
            "category": ObjectCategory.PHYSICAL,
            "binding": {
                "source_path": "rules/checks.py",
                "qualified_name": "check",
                "source_digest": "a" * 64,
            },
        },
    )


def test_list_verbs_returns_empty_collection_when_no_verb_is_marked() -> None:
    plain = BindingRef("rules/plain.py", "check", "b" * 64)
    objects = _objects()
    state = BindingState(objects.objects, (BindingEntry("alpha", plain),))

    assert list_verbs(QueryState(state)) == ()


def test_object_detail_projects_sources_binding_relations_truth_and_justification() -> None:
    objects = _objects()
    attribute_state = set_attributes(AttributeState(objects), "zeta", {"level": 12})
    tags = add_explicit_tag((), "zeta", "ready")
    tags = sync_adj_tags(tags, "zeta", "level", (), ("ready",))
    relation_key = NodeKey.svk("zeta", "alpha", "c" * 64)
    relation = RelationFact(
        SVK("zeta", "alpha", ("monitor",), (("target", "alpha"),)),
        relation_key.encode(),
    )
    kernel = attribute_state.kernel
    assert kernel is not None
    kernel.register_node(TruthNode(NodeKey.tag("zeta", "ready")))
    kernel.register_node(TruthNode(relation_key))
    kernel.add_justification(
        Justification(
            "level-implies-ready",
            NodeKey.tag("zeta", "ready"),
            (Premise(NodeKey.adj("zeta", "level")),),
        )
    )
    kernel.assert_assumption(Assumption("relation-explicit", relation_key))
    kernel.propagate()
    state = QueryState(
        objects,
        attribute_state.attributes,
        tags,
        (relation,),
        kernel,
    )

    detail = get_object_detail(state, "zeta")

    assert detail.name == "zeta"
    assert detail.category is ObjectCategory.PHYSICAL
    assert detail.is_verb
    assert detail.binding is not None
    assert detail.binding.source_path == "rules/checks.py"
    assert detail.attributes[0].key == "level"
    assert detail.attributes[0].value == 12
    assert detail.attributes[0].sources[0].kind == "explicit"
    assert detail.tags[0].name == "ready"
    assert tuple(source.kind for source in detail.tags[0].sources) == (
        "derived",
        "explicit",
    )
    assert detail.relations[0].node_key == relation_key.encode()
    assert detail.relations[0].args == ("monitor",)
    truths = {truth.node_key: truth for truth in detail.truths}
    assert truths[NodeKey.subject("zeta").encode()].value is TruthValue.TRUE
    assert truths[NodeKey.adj("zeta", "level").encode()].value is TruthValue.TRUE
    assert truths[NodeKey.tag("zeta", "ready").encode()].supports[0].support_id == (
        "level-implies-ready"
    )
    assert truths[relation_key.encode()].supports[0].support_id == "relation-explicit"


def test_object_detail_rejects_unknown_name_without_mutating_query_state() -> None:
    state = QueryState(_objects())
    before = list_objects(state)

    with pytest.raises(ObjectNotFoundError, match="unknown object: missing"):
        get_object_detail(state, "missing")

    assert list_objects(state) == before


def test_repeated_queries_do_not_write_state_or_execute_binding(tmp_path: Path) -> None:
    marker = tmp_path / "binding-ran"
    rules = tmp_path / "rules"
    rules.mkdir()
    source = rules / "side_effect.py"
    source.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('ran')\n"
        "def check(subject):\n"
        "    return True\n",
        encoding="utf-8",
    )
    scope = ProjectScope(tmp_path)
    repository = StateRepository(scope)
    repository.save(StateDocument(revision=1, objects=({"name": "zeta"},)))
    before_bytes = scope.state_path.read_bytes()
    before_mtime = scope.state_path.stat().st_mtime_ns

    objects = _objects()
    side_effect_binding = BindingRef(
        "rules/side_effect.py",
        "check",
        "d" * 64,
        is_verb=True,
    )
    query = QueryState(
        BindingState(
            objects.objects,
            (BindingEntry("zeta", side_effect_binding),),
        )
    )
    first = (
        list_objects(query),
        list_verbs(query),
        get_object_detail(query, "zeta"),
    )
    second = (
        list_objects(query),
        list_verbs(query),
        get_object_detail(query, "zeta"),
    )

    assert first == second
    assert scope.state_path.read_bytes() == before_bytes
    assert scope.state_path.stat().st_mtime_ns == before_mtime
    assert not marker.exists()
