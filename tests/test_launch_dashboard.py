from unittest.mock import Mock

import pytest

from freight_intelligence import launch_dashboard as launcher


def test_existing_dashboard_is_reused_without_spawning(monkeypatch):
    monkeypatch.setattr(launcher, "healthy", lambda port: True)
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    assert launcher.ensure_dashboard() == ("http://127.0.0.1:8501/", False)
    spawn.assert_not_called()


def test_occupied_port_is_not_killed_or_replaced(monkeypatch):
    monkeypatch.setattr(launcher, "healthy", lambda port: False)
    monkeypatch.setattr(launcher, "occupied", lambda port: True)
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    with pytest.raises(RuntimeError, match="ocupada"):
        launcher.ensure_dashboard()
    spawn.assert_not_called()


def test_launch_waits_for_health_and_binds_only_loopback(tmp_path, monkeypatch):
    (tmp_path / "dashboards").mkdir()
    (tmp_path / "dashboards/app.py").write_text("")
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    states = iter([False, False, True])
    monkeypatch.setattr(launcher, "healthy", lambda port: next(states))
    monkeypatch.setattr(launcher, "occupied", lambda port: False)
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: None)
    spawn = Mock(return_value=Mock(poll=Mock(return_value=None)))
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    assert launcher.ensure_dashboard() == ("http://127.0.0.1:8501/", True)
    command = spawn.call_args.args[0]
    assert command[command.index("--server.address") + 1] == "127.0.0.1"
    assert "pipeline" not in " ".join(command)


@pytest.mark.parametrize("port", [0, 80, 65536, True])
def test_invalid_port_rejected(port):
    with pytest.raises(ValueError):
        launcher.ensure_dashboard(port)
