import json
import os
import shutil
import tempfile
from click.testing import CliRunner
import pytest

from symbox.cli import cli


@pytest.fixture
def cli_runner(monkeypatch):
    dir_path = tempfile.mkdtemp(prefix="sbox_cli_test_")
    monkeypatch.chdir(dir_path)
    runner = CliRunner()
    yield runner
    shutil.rmtree(dir_path, ignore_errors=True)


def test_cli_create_and_list(cli_runner):
    res = cli_runner.invoke(cli, ["create", "robot", "--kind", "physical"])
    assert res.exit_code == 0
    assert "created: robot (physical)" in res.output

    res_list = cli_runner.invoke(cli, ["list", "objects"])
    assert res_list.exit_code == 0
    assert "robot (physical)" in res_list.output


def test_cli_set_and_threshold_confirm(cli_runner):
    cli_runner.invoke(cli, ["create", "laptop"])

    # Set Broken=true
    res1 = cli_runner.invoke(cli, ["set", "laptop", "{'Broken': true}"])
    assert res1.exit_code == 0
    assert "updated: laptop" in res1.output

    # Set Fixed=true without --force -> triggers confirm_needed JSON (spec v0.4 §2.5)
    res2 = cli_runner.invoke(cli, ["set", "laptop", "{'Fixed': true}"])
    assert res2.exit_code == 0
    conf = json.loads(res2.output)
    assert conf["status"] == "confirm_needed"
    assert conf["target"] == "laptop"
    assert conf["existing"] == "Broken"
    assert conf["proposed"] == "Fixed"
    assert "question" in conf

    # Set Fixed=true with --force -> succeeds
    res3 = cli_runner.invoke(cli, ["set", "laptop", "{'Fixed': true}", "--force"])
    assert res3.exit_code == 0
    assert "updated: laptop" in res3.output


def test_cli_svo_and_backup(cli_runner):
    cli_runner.invoke(cli, ["create", "robot"])
    cli_runner.invoke(cli, ["create", "task"])

    # Assert SVO
    res_svo = cli_runner.invoke(cli, ["svo", "robot", "Operates", "task"])
    assert res_svo.exit_code == 0
    assert "asserted: robot Operates task" in res_svo.output

    # Backup create
    res_b1 = cli_runner.invoke(cli, ["backup", "create", "v1.0"])
    assert res_b1.exit_code == 0
    assert "backup created: v1.0" in res_b1.output

    # Backup log
    res_log = cli_runner.invoke(cli, ["backup", "log"])
    assert res_log.exit_code == 0
    assert "v1.0" in res_log.output


def test_cli_error_output(cli_runner):
    # Deleting a missing object -> error on stderr-ish output + non-zero exit
    res = cli_runner.invoke(cli, ["delete", "ghost"])
    assert res.exit_code == 1
    assert "error: object 'ghost' not found" in res.output


def test_cli_slash_prefix_handling(cli_runner):
    # Test slash prefix in object arguments and subcommands
    res = cli_runner.invoke(cli, ["create", "/person"])
    assert res.exit_code == 0
    assert "created: person (physical)" in res.output
