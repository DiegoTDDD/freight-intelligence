"""Prepare a small allowlisted dashboard snapshot; never copy raw data or credentials."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from freight_intelligence.dashboard_data import load_projection_bundle
from freight_intelligence.evaluation_results import load_temporal_report

ROOT = Path(__file__).resolve().parents[1]
GOLD_FILES = (
    "annual_kpis.parquet", "annual_growth.parquet", "annual_cagr.parquet", "mode_mix.parquet",
    "commodity_mix.parquet", "commodity_lookup.parquet", "commodity_growth.parquet",
    "commodity_share_change.parquet", "top_corridors.parquet", "corridor_summary.parquet",
    "corridor_concentration.parquet",
)


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Snapshot destination already exists; choose a new directory")
    paths = [Path("data/gold/faf5") / name for name in GOLD_FILES]
    readme = Path("data/raw/faf5/forecast/bts_FAF_HiLoForecasts_README_20230929.txt")
    if (root / readme).is_file():
        paths.append(readme)
    if (root / "models/faf5/annual/metadata.json").is_file():
        load_projection_bundle(root)
        paths.extend(Path("models/faf5/annual") / name for name in
                     ("metadata.json", "forecast.parquet", "evaluation.parquet"))
    if (root / "artifacts/evaluation/annual/metadata.json").is_file():
        load_temporal_report(root / "artifacts/evaluation/annual", root / "data/gold/faf5/annual_kpis.parquet")
        paths.extend(Path("artifacts/evaluation/annual") / name for name in
                     ("metadata.json", "predictions.parquet", "scores.parquet"))
    total = 0
    for path in paths:
        size = (root / path).stat().st_size
        if size > 10 * 1024 * 1024:
            raise ValueError(f"Snapshot file exceeds 10 MiB: {path}")
        total += size
    if total > 30 * 1024 * 1024:
        raise ValueError("Snapshot exceeds 30 MiB")
    output.mkdir(parents=True)
    records = []
    try:
        for path in paths:
            target = output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = (root / path).read_bytes()
            if path.name == "metadata.json":
                metadata = json.loads(data)
                metadata.pop("input", None)  # Do not publish the local machine's absolute path.
                data = (json.dumps(metadata, indent=2, allow_nan=False) + "\n").encode()
            target.write_bytes(data)
            records.append({"path": path.as_posix(), "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
        manifest = {"source": "Local analytical aggregates derived from public FAF5.5.1",
                    "interpretation": "Includes scenario projection years; not observed future demand",
                    "excluded": "Raw datasets, Silver, credentials and saved transport scenarios",
                    "files": records}
        (output / "snapshot_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    except Exception:
        if output.resolve() != output:
            raise RuntimeError("Snapshot cleanup refused: destination path changed") from None
        shutil.rmtree(output)
        raise
    return len(records), total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "deployment/preview_data")
    args = parser.parse_args()
    try:
        count, size = prepare(ROOT, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Snapshot preparation failed: {error}\n")
    print(f"Prepared {count} allowlisted files ({size} source bytes); no upload or deployment.")


if __name__ == "__main__":
    main()
