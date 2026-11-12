"""Archive a committed revision and verify its bundled analytical snapshot."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "LogiNexus/"


def verify_archive(archive):
    with ZipFile(archive) as bundle:
        for name in bundle.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts or "\\" in name:
                raise ValueError(f"Unsafe archive path: {name}")
            if any(part in {".git", ".env", "secrets"} for part in path.parts):
                raise ValueError(f"Private path in archive: {name}")
        manifest = json.loads(bundle.read(PREFIX + "deployment/preview_data/snapshot_manifest.json"))
        for record in manifest["files"]:
            path = PurePosixPath(record["path"])
            if (path.is_absolute() or PureWindowsPath(record["path"]).drive
                    or ".." in path.parts or "\\" in record["path"]):
                raise ValueError("Unsafe snapshot path")
            data = bundle.read(PREFIX + "deployment/preview_data/" + record["path"])
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise ValueError(f"Snapshot hash mismatch: {path}")
        count = len(manifest["files"])
        for directory, filename in (("brazil_data", "provenance.json"),
                                    ("brazil_modes", "provenance.json"),
                                    ("route_examples", "manifest.json")):
            base = PREFIX + f"deployment/{directory}/"
            if base + filename not in bundle.namelist():
                continue  # Earlier committed revisions may not include these features.
            additional = json.loads(bundle.read(base + filename))
            for record in additional["files"]:
                path = PurePosixPath(record["path"])
                if len(path.parts) != 1 or PureWindowsPath(record["path"]).drive or "\\" in record["path"]:
                    raise ValueError("Unsafe additional snapshot path")
                if hashlib.sha256(bundle.read(base + record["path"])).hexdigest() != record["sha256"]:
                    raise ValueError(f"Additional snapshot hash mismatch: {path}")
                count += 1
        if not manifest["files"] or bundle.testzip() is not None:
            raise ValueError("Invalid archive integrity")
        return count


def package_recovery(destination, revision="HEAD", root=ROOT):
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=root, text=True,
    ).strip()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"LogiNexus-recuperacao-{commit[:12]}.zip"
    checksum_path = archive.with_suffix(".zip.sha256")
    if archive.exists() or checksum_path.exists():
        raise FileExistsError("Recovery package already exists; choose another destination")
    with tempfile.TemporaryDirectory(prefix="loginexus-recovery-") as staging:
        staged = Path(staging) / archive.name
        subprocess.run(
            ["git", "archive", "--format=zip", f"--prefix={PREFIX}",
             f"--output={staged}", commit], cwd=root, check=True,
        )
        with ZipFile(staged, "a") as bundle:
            guide = bundle.read(PREFIX + "docs/recovery.md")
            bundle.writestr("RECUPERAR.md", guide)
            bundle.writestr("REVISION.txt", commit + "\n")
        count = verify_archive(staged)
        checksum = hashlib.sha256(staged.read_bytes()).hexdigest()
        # Exclusive creation preserves any independently created backup.
        with archive.open("xb") as output, staged.open("rb") as source:
            import shutil

            shutil.copyfileobj(source, output)
        with checksum_path.open("x", encoding="ascii") as output:
            output.write(f"{checksum}  {archive.name}\n")
    return {"archive": str(archive), "commit": commit, "sha256": checksum,
            "verified_snapshot_files": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    print(json.dumps(package_recovery(args.output, args.revision), indent=2))


if __name__ == "__main__":
    main()
