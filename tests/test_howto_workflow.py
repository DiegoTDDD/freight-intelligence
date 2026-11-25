"""Inject command failures into the actual heavy-workflow shell blocks, without data."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/howto-check.yml"


def workflow_block(command):
    text = WORKFLOW.read_text(encoding="utf-8")
    for block in re.findall(r"        run: \|\n((?:          .*\n|\n)+)", text):
        if command in block:
            return "\n".join(line[10:] for line in block.splitlines()) + "\n"
    raise AssertionError(f"Missing workflow command {command}")


def bash_path():
    if os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        return str(candidate) if candidate.is_file() else None
    return shutil.which("bash")


@pytest.mark.parametrize("command", ["python -m freight_intelligence.pipeline", "python -m pytest"])
@pytest.mark.parametrize("exit_code", [0, 17])
def test_actual_workflow_preserves_failure_and_log(command, exit_code, tmp_path):
    bash = bash_path()
    if bash is None:
        pytest.skip("Bash is required for the GitHub shell regression check")
    (tmp_path / "data/gold/faf5").mkdir(parents=True)
    fake = (
        "python() { printf 'diagnostic on stdout\\n'; "
        f"printf 'diagnostic on stderr\\n' >&2; return {exit_code}; }}\n"
    )
    environment = dict(os.environ)
    environment.pop("BASH_ENV", None)
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-eo", "pipefail"],
        input=fake + workflow_block(command) + "printf 'downstream reached\\n'\n",
        text=True, capture_output=True, cwd=tmp_path, env=environment, timeout=15, check=False,
    )
    assert result.returncode == exit_code, result.stderr
    assert "diagnostic on stdout" in result.stdout
    assert "diagnostic on stderr" in result.stdout
    assert ("downstream reached" in result.stdout) == (exit_code == 0)
    log = tmp_path / ("pipeline.log" if "pipeline" in command else "pytest.log")
    assert "diagnostic on stderr" in log.read_text()


def test_heavy_run_requires_manual_dispatch():
    text = WORKFLOW.read_text(encoding="utf-8")
    events = text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in events
    assert "push:" not in events and "schedule:" not in events
    assert "shell: bash" in text
