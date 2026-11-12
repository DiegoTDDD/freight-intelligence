import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "package_recovery", Path(__file__).resolve().parents[1] / "scripts/package_recovery.py",
)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_committed_archive_excludes_local_changes_and_refuses_overwrite(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    snapshot = repo / "deployment/preview_data"
    snapshot.mkdir(parents=True)
    (snapshot / "sample.txt").write_bytes(b"committed data")
    (snapshot / "snapshot_manifest.json").write_text(json.dumps({"files": [{
        "path": "sample.txt", "sha256": hashlib.sha256(b"committed data").hexdigest(),
    }]}))
    (repo / "docs").mkdir()
    (repo / "docs/recovery.md").write_text("Recovery guide")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                    "commit", "-qm", "fixture"], cwd=repo, check=True)
    (snapshot / "sample.txt").write_bytes(b"uncommitted change")
    (repo / ".env").write_text("PRIVATE=not-for-backup")
    result = recovery.package_recovery(tmp_path / "output", root=repo)
    assert result["verified_snapshot_files"] == 1
    with ZipFile(result["archive"]) as bundle:
        assert bundle.read("LogiNexus/deployment/preview_data/sample.txt") == b"committed data"
        assert bundle.read("RECUPERAR.md") == b"Recovery guide"
        assert not any(name.endswith("/.env") for name in bundle.namelist())
    with pytest.raises(FileExistsError):
        recovery.package_recovery(tmp_path / "output", root=repo)


@pytest.mark.parametrize("private_path", ["../escape", "LogiNexus/.env", "C:\\escape"])
def test_rejects_unsafe_or_private_paths(tmp_path, private_path):
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr(private_path, "private")
    with pytest.raises(ValueError):
        recovery.verify_archive(archive)


def test_rejects_changed_snapshot_bytes(tmp_path):
    archive = tmp_path / "changed.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("LogiNexus/deployment/preview_data/sample", "changed")
        bundle.writestr("LogiNexus/deployment/preview_data/snapshot_manifest.json",
                        json.dumps({"files": [{"path": "sample", "sha256": "wrong"}]}))
    with pytest.raises(ValueError, match="hash mismatch"):
        recovery.verify_archive(archive)
