import shutil
import tempfile
import time
import pytest

from symbox.core.engine import SymboxEngine
from symbox.core.meta import Worry
from symbox.core.subject import Subject


@pytest.fixture
def tmp_sbox_dir():
    dir_path = tempfile.mkdtemp(prefix="sbox_perf_")
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


def test_large_graph_scaling_performance(tmp_sbox_dir):
    """Stress test: 1,000 Subjects and 1,000 unique SVO assertions propagation speed."""
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)

    num_subjects = 1000
    num_assertions = 999

    start_time = time.perf_counter()

    # Batch create subjects
    for i in range(num_subjects):
        engine.create_subject(f"node_{i}", kind="physical")

    create_time = time.perf_counter() - start_time

    # Create verb
    engine.create_verb("Connects")

    start_svo = time.perf_counter()
    for i in range(num_assertions):
        s_name = f"node_{i}"
        o_name = f"node_{i + 1}"
        success, _ = engine.assert_svo(s_name, "Connects", o_name, if_force=False)
        assert success is True

    svo_time = time.perf_counter() - start_svo

    total_time = time.perf_counter() - start_time
    assert len(engine.subjects) == num_subjects
    assert len(engine.svo_triples) == num_assertions

    print(f"\n[PERF] Created {num_subjects} nodes in {create_time:.4f}s ({num_subjects / create_time:.0f} nodes/sec)")
    print(f"[PERF] Asserted {num_assertions} SVO triples in {svo_time:.4f}s ({num_assertions / svo_time:.0f} SVO/sec)")
    print(f"[PERF] Total benchmark time: {total_time:.4f}s")


def test_rapid_worry_observation_performance(tmp_sbox_dir):
    """Stress test: 100 Worry observers monitoring 1,000 attribute state updates."""
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)

    num_worries = 100
    num_updates = 1000

    robot = engine.create_subject("robot", kind="physical")

    for i in range(num_worries):
        limit = 0.1 + (i * 0.005)
        worry = Worry(
            name=f"BatteryWorry_{i}",
            watch_subject_name="robot",
            condition_func=lambda s, l=limit: s.attributes.get("battery", 1.0) < l,
        )
        worry.engine_callback = engine._on_worry_triggered
        engine.subjects[f"BatteryWorry_{i}"] = worry
        robot.register_worry_observer(worry)

    start_time = time.perf_counter()
    for u in range(num_updates):
        level = (u % 100) / 100.0
        robot.set_attribute("battery", level)

    duration = time.perf_counter() - start_time
    ops_per_sec = (num_updates * num_worries) / duration
    print(f"\n[PERF] Executed {num_updates} attribute updates across {num_worries} Worry observers in {duration:.4f}s ({ops_per_sec:.0f} worry checks/sec)")


def test_backup_and_rollback_stress(tmp_sbox_dir):
    """Stress test: 30 sequential snapshot creations and rollbacks."""
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)

    num_snapshots = 30
    start_time = time.perf_counter()

    for i in range(num_snapshots):
        engine.create_subject(f"item_{i}")
        tag = engine.backup.create(f"snap_{i}")
        assert tag == f"snap_{i}"

    history = engine.backup.log()
    assert len(history) == num_snapshots

    # Rollback to first snapshot
    res = engine.backup.rollback("snap_0")
    assert res is True
    engine.load_state()

    duration = time.perf_counter() - start_time
    print(f"\n[PERF] Created and verified {num_snapshots} snapper git backups & rollback in {duration:.4f}s")


def test_belief_revision_contradiction_stress(tmp_sbox_dir):
    """Stress test: 200 conflicting SVO assertions with belief revision (--if-force)."""
    engine = SymboxEngine(sbox_dir=tmp_sbox_dir)
    engine.create_subject("robot")
    engine.create_subject("apple")

    verb = engine.create_verb("Eats")
    verb.veto_rules.append("Rotten")

    start_time = time.perf_counter()
    num_conflicts = 200

    for i in range(num_conflicts):
        rotten_val = (i % 2 == 0)
        engine.set_attributes("apple", {"Rotten": rotten_val}, force=True)
        # Force assertion during veto condition
        success, _ = engine.assert_svo("robot", "Eats", "apple", if_force=True)
        assert success is True

    duration = time.perf_counter() - start_time
    print(f"\n[PERF] Handled {num_conflicts} belief revision contradictions in {duration:.4f}s ({num_conflicts / duration:.0f} revisions/sec)")
