"""Download the public datasets used by FactoryPulse."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
RAW_DIR = ROOT / "data" / "raw"
DATASETS = {
    "ims": {
        "url": "https://data.nasa.gov/docs/legacy/IMS.zip",
        "directory": RAW_DIR / "ims_bearings",
        "expected": ("1st_test", "2nd_test", "3rd_test"),
    },
    "ai4i": {
        "url": (
            "https://archive.ics.uci.edu/static/public/601/"
            "ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset.zip"
        ),
        "directory": RAW_DIR / "ai4i_2020",
        "expected": ("ai4i2020.csv", "ai4i_2020.csv"),
    },
}
CMAPSS_FILE = RAW_DIR / "train_FD001.txt"


def _download(url: str, destination: Path) -> None:
    """Stream a URL to disk without keeping the archive in memory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FactoryPulse dataset setup (local development)"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def _safe_extract(archive_path: Path, destination: Path) -> None:
    """Extract a ZIP only when every member stays inside its target directory."""
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as error:
                raise ValueError(
                    f"Archive member escapes extraction directory: {member.filename}"
                ) from error
        archive.extractall(destination)


def _download_archive(name: str) -> None:
    info = DATASETS[name]
    destination: Path = info["directory"]
    expected = info["expected"]
    if any(any(destination.rglob(filename)) for filename in expected):
        print(f"{name}: already present in {destination.relative_to(ROOT)}")
        return

    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f"{name}-", suffix=".zip", dir=destination, delete=False
    ) as temp_file:
        archive_path = Path(temp_file.name)
    try:
        print(f"{name}: downloading published archive")
        _download(info["url"], archive_path)
        _safe_extract(archive_path, destination)
        if not any(any(destination.rglob(filename)) for filename in expected):
            raise RuntimeError(
                f"The {name} archive downloaded, but expected files were not found."
            )
        print(f"{name}: extracted to {destination.relative_to(ROOT)}")
    finally:
        archive_path.unlink(missing_ok=True)


def _prepare_cmapss() -> None:
    if CMAPSS_FILE.is_file():
        print(f"cmapss: using existing {CMAPSS_FILE.relative_to(ROOT)}")
        return

    url = os.environ.get("CMAPSS_URL", "").strip()
    if not url:
        raise RuntimeError(
            "C-MAPSS is not present. Set CMAPSS_URL to an authorized ZIP archive "
            "URL and rerun this command."
        )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="factorypulse-cmapss-") as temp_dir:
        archive_path = Path(temp_dir) / "cmapss.zip"
        _download(url, archive_path)
        extraction_dir = Path(temp_dir) / "extracted"
        _safe_extract(archive_path, extraction_dir)
        candidates = list(extraction_dir.rglob("train_FD001.txt"))
        if not candidates:
            raise RuntimeError(
                "The C-MAPSS archive does not contain train_FD001.txt."
            )
        shutil.copy2(candidates[0], CMAPSS_FILE)
    print(f"cmapss: extracted {CMAPSS_FILE.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=("all", "cmapss", "ims", "ai4i"),
        default="all",
        help="Dataset to prepare (default: all)",
    )
    args = parser.parse_args()

    selected = ("cmapss", "ims", "ai4i") if args.dataset == "all" else (args.dataset,)
    for name in selected:
        if name == "cmapss":
            _prepare_cmapss()
        else:
            _download_archive(name)


if __name__ == "__main__":
    main()
