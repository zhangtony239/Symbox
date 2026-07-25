import os
import shutil
import tempfile
import pytest

from symbox.core.adj import Adj
from symbox.core.backup import BackupManager
from symbox.core.embedding import EmbeddingDetector
from symbox.core.engine import SymboxEngine
from symbox.core.ltms_wrapper import ContradictionError, LTMSWrapper
from symbox.core.meta import Attention, Worry
from symbox.core.subject import Subject
from symbox.core.verb import Verb


@pytest.fixture
def tmp_sbox_dir():
    dir_path = tempfile.mkdtemp(prefix="sbox_test_")
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


def test_subject_and_adj():
    adj_broken = Adj(name="Broken", value=True, implies_tags=["damaged", "electronic"])
    subj = Subject(name="laptop", kind="physical", adj={"Broken": adj_broken})

    assert subj.name == "laptop"
    assert "Broken" in subj.adj
    assert "electronic" in subj.tags
    assert "damaged" in subj.tags

    subj.set_attribute("battery", 0.15)
    assert subj.attributes["battery"] == 0.15


def test_verb_kind_validation():
    verb_eats = Verb(name="Eats", domain={"physical"}, range_={"physical"})

    valid, msg = verb_eats.validate_kinds("physical", "physical")
    assert valid is True

    valid, msg = verb_eats.validate_kinds("meta", "physical")
    assert valid is False
    assert "domain" in msg


def test_worry_observer_and_symbol_compilation(tmp_sbox_dir):
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)
    robot = engine.create_subject("robot", kind="physical")

    # Define low battery condition function
    def low_battery_condition(s: Subject) -> bool:
        return s.attributes.get("battery", 1.0) < 0.2

    worry = Worry(name="LowBattery", watch_subject_name="robot", condition_func=low_battery_condition)
    worry.engine_callback = engine._on_worry_triggered
    engine.subjects["LowBattery"] = worry
    robot.register_worry_observer(worry)

    # Initial state battery = 1.0
    robot.set_attribute("battery", 0.9)
    assert worry.is_active is False
    assert engine.ltms.get_node_label("Worry:LowBattery") == "UNKNOWN"

    # Battery drops to 0.1 -> triggers Worry
    robot.set_attribute("battery", 0.1)
    assert worry.is_active is True
    assert engine.ltms.get_node_label("Worry:LowBattery") == "TRUE"


def test_veto_rule_contradiction(tmp_sbox_dir):
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)
    robot = engine.create_subject("robot", kind="physical")
    apple = engine.create_subject("apple", kind="physical")

    eats = engine.create_verb("Eats")
    eats.veto_rules.append("Rotten")

    # Set apple as Rotten
    engine.set_attributes("apple", {"Rotten": True}, force=True)

    # Assert Eats(robot, apple) should fail due to veto rule
    success, msg = engine.assert_svo("robot", "Eats", "apple", if_force=False)
    assert success is False
    assert "LTMS Contradiction" in msg or "evaluated to False" in msg or "veto" in msg

    # With if_force=True, it should force assertion
    success_forced, msg_forced = engine.assert_svo("robot", "Eats", "apple", if_force=True)
    assert success_forced is True


def test_embedding_threshold_fallback():
    detector = EmbeddingDetector()
    # "Fixed" vs "Broken" opposite test
    needs_conf, conf_data = detector.check_threshold("laptop", "Fixed", ["Broken"])
    assert needs_conf is True
    assert conf_data["status"] == "confirm_needed"
    assert conf_data["target"] == "laptop"
    assert conf_data["existing"] == "Broken"
    assert conf_data["proposed"] == "Fixed"


def test_backup_manager(tmp_sbox_dir):
    backup = BackupManager(sbox_dir=tmp_sbox_dir)
    tag1 = backup.create("initial_snapshot")
    assert tag1 == "initial_snapshot"

    logs = backup.log()
    assert len(logs) >= 1
    assert logs[0]["note"] == "initial_snapshot"

    # Modify state file
    with open(backup.state_file, "w") as f:
        f.write('{"modified": true}')

    # Rollback
    res = backup.rollback("initial_snapshot")
    assert res is True

    with open(backup.state_file, "r") as f:
        data = f.read()
        assert "modified" not in data
