import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from freight_intelligence.utils.runtime_lock import normalize, read_lock, version_differences

ROOT = Path(__file__).resolve().parents[1]


def test_committed_lock_satisfies_declared_api_runtime_requirements():
    pins = read_lock(ROOT / "requirements/api-linux-py313.lock")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = project["dependencies"] + project["optional-dependencies"]["api"]
    for text in requirements:
        requirement = Requirement(text)
        assert normalize(requirement.name) in pins
        assert pins[normalize(requirement.name)] in requirement.specifier


def test_distribution_names_normalize_and_build_tools_are_excluded():
    expected = {"example-lib": "1.2.3"}
    installed = {"Example_Lib": "1.2.3", "pip": "25.0", "freight_intelligence": "0.1.0"}
    assert version_differences(expected, installed) == []


def test_missing_mismatched_and_unpinned_packages_are_reported():
    differences = version_differences(
        {"missing": "1", "changed": "2"}, {"changed": "3", "unexpected": "4"}
    )
    assert differences == [
        "Version mismatch: changed expected 2, installed 3",
        "Missing: missing==1",
        "Unpinned runtime package: unexpected",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# only comments\n",
        "example>=1",
        "-r other.txt",
        "https://example.com/package.whl",
        "Example_lib==1\nexample-lib==2",
        "pip==25.0",
        "-e .",
    ],
)
def test_lock_rejects_ambiguous_or_nonruntime_entries(tmp_path, text):
    path = tmp_path / "runtime.lock"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_lock(path)


def test_comments_and_blank_lines_are_allowed(tmp_path):
    path = tmp_path / "runtime.lock"
    path.write_text("# description\n\nExample_lib==1.2.3\n")
    assert read_lock(path) == {"example-lib": "1.2.3"}


def test_dashboard_lock_supports_streamlit_and_all_app_requirements():
    pins = read_lock(ROOT / "requirements/dashboard-linux-py313.lock")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    for text in project["dependencies"] + project["optional-dependencies"]["app"]:
        requirement = Requirement(text)
        assert pins[normalize(requirement.name)] in requirement.specifier
    assert pins["streamlit"] == "1.62.0"
    assert pins["pyarrow"] == "25.0.1"
    assert pins["websockets"].startswith("16.")
