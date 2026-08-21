from freight_intelligence.config.settings import (
    PROJECT_ROOT,
    RAW_DATA_DIR,
    FAF_RAW_DIR,
)


def test_project_root_exists():
    assert PROJECT_ROOT.exists()


def test_raw_data_directory_exists():
    assert RAW_DATA_DIR.exists()


def test_faf_directory_exists():
    assert FAF_RAW_DIR.exists()