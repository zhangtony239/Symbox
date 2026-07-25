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
    data = json.loads(res.output)
    assert data["status"] == "success"
    assert data["object"]["name"] == "robot"

    res_list = cli_runner.invoke(cli, ["list", "objects"])
    assert res_list.exit_code == 0
    list_data = json.loads(res_list.output)
    assert len(list_data) == 1
    assert list_data[0]["name"] == "robot"


def test_cli_set_and_threshold_confirm(cli_runner):
    cli_runner.invoke(cli, ["create", "laptop"])

    # Set Broken=true
    res1 = cli_runner.invoke(cli, ["set", "laptop", "{'Broken': true}"])
    assert res1.exit_code == 0
    data1 = json.loads(res1.output)
    assert data1["status"] == "success"

    # Set Fixed=true without --force -> triggers confirm_needed JSON
    res2 = cli_runner.invoke(cli, ["set", "laptop", "{'Fixed': true}"])
    assert res2.exit_code == 0
    data2 = json.loads(res2.output)
    assert data2["status"] == "confirm_needed"
    assert data2["existing"] == "Broken"
    assert data2["proposed"] == "Fixed"

    # Set Fixed=true with --force -> succeeds
    res3 = cli_runner.invoke(cli, ["set", "laptop", "{'Fixed': true}", "--force"])
    assert res3.exit_code == 0
    data3 = json.loads(res3.output)
    assert data3["status"] == "success"


def test_cli_svo_and_backup(cli_runner):
    cli_runner.invoke(cli, ["create", "robot"])
    cli_runner.invoke(cli, ["create", "task"])

    # Assert SVO
    res_svo = cli_runner.invoke(cli, ["svo", "robot", "Operates", "task"])
    assert res_svo.exit_code == 0
    data_svo = json.loads(res_svo.output)
    assert data_svo["status"] == "success"

    # Backup create
    res_b1 = cli_runner.invoke(cli, ["backup", "create", "v1.0"])
    assert res_b1.exit_code == 0

    # Backup log
    res_log = cli_runner.invoke(cli, ["backup", "log"])
    assert res_log.exit_code == 0
    history = json.loads(res_log.output)
    assert len(history) >= 1
    assert history[0]["note"] == "v1.0"


def test_cli_slash_prefix_handling(cli_runner):
    # Test slash prefix in object arguments and subcommands
    res = cli_runner.invoke(cli, ["create", "/person"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["status"] == "success"
    assert data["object"]["name"] == "person"
