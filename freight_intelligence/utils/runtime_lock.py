"""Verify the installed Linux API runtime against its version manifest."""

import argparse
import importlib.metadata
import platform
import re
import sys
from pathlib import Path

BUILD_PACKAGES = {"pip", "setuptools", "wheel", "freight-intelligence"}


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path) -> dict[str, str]:
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9_.+!-]+)", line)
        if match is None:
            raise ValueError(f"Line {number}: require an exact name==version pin")
        name, version = normalize(match[1]), match[2]
        if name in result:
            raise ValueError(f"Duplicate dependency: {name}")
        if name in BUILD_PACKAGES:
            raise ValueError(f"Application/build package does not belong in runtime lock: {name}")
        result[name] = version
    if not result:
        raise ValueError("Runtime lock is empty")
    return result


def version_differences(expected: dict[str, str], installed: dict[str, str]) -> list[str]:
    installed = {normalize(name): version for name, version in installed.items()}
    differences = []
    for name, version in sorted(expected.items()):
        if name not in installed:
            differences.append(f"Missing: {name}=={version}")
        elif installed[name] != version:
            differences.append(
                f"Version mismatch: {name} expected {version}, installed {installed[name]}"
            )
    for name in sorted(installed.keys() - expected.keys() - BUILD_PACKAGES):
        differences.append(f"Unpinned runtime package: {name}")
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "requirements/api-linux-py313.lock",
    )
    args = parser.parse_args(argv)
    if sys.platform != "linux" or sys.version_info[:2] != (3, 13) or platform.machine() != "x86_64":
        parser.exit(2, "This runtime lock targets Linux x86_64 with CPython 3.13.\n")
    try:
        expected = read_lock(args.lock)
        installed = {
            dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
        }
        differences = version_differences(expected, installed)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Runtime verification failed: {error}\n")
    if differences:
        parser.exit(1, "\n".join(differences) + "\n")
    print(f"Verified {len(expected)} pinned API runtime packages.")


if __name__ == "__main__":
    main()
