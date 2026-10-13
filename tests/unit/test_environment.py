import json
from pathlib import Path

from typer.testing import CliRunner

from bitebench.cli import app
from bitebench.environment import command_probe, doctor


def test_missing_command_is_explicit():
    assert (
        command_probe(["bite_nonexistent_probe_executable"])["reason_code"]
        == "COMMAND_NOT_FOUND"
    )


def test_missing_data_directory_does_not_crash(tmp_path):
    result = doctor(tmp_path / "missing")
    assert result["data_directory"]["ok"] is False
    assert result["ok"] is False


def test_cli_doctor_json():
    result = CliRunner().invoke(app, ["env", "doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {
        "python",
        "platform",
        "gpu",
        "torch",
        "ollama",
        "data_directory",
    } <= payload.keys()
    assert Path("data").is_dir()
