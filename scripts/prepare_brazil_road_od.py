"""Rebuild the small reviewed state-pair CSV without querying or rerunning FAF."""

import hashlib
from pathlib import Path

from freight_intelligence.brazil_road_od import DEFAULT_ROOT, parse_capture, read_contract


def prepare(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = read_contract(root)
    for entry in metadata["files"]:
        if entry["path"] == "state_od.csv":
            continue
        raw = (root / entry["path"]).read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Changed ANTT state-pair source evidence")
    data = parse_capture((root / "state_od_capture.json").read_bytes())
    raw = data.write_csv().encode()
    expected = next(entry for entry in metadata["files"] if entry["path"] == "state_od.csv")
    if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise ValueError("Rebuilt ANTT table differs from review")
    (root / "state_od.csv").write_bytes(raw)
    return data


if __name__ == "__main__":
    print(f"Prepared {prepare().height} reviewed ANTT state pairs")
