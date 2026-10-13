"""Create/validate isolated specimens for compact label print-layout QA."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sample_labels import labels_document

OUTPUT = ROOT / ".tools/tmp/labels-separated-qa"
CASES = {
    "short-16": ("SPMC/03/2026", [f"Product {index:03d} Calcium Carbonate BP" for index in range(1, 17)]),
    "mixed-20": ("SPMC/03/2026", [f"Product {index:03d} " +
        ("Benzhexol Hydrochloride BP 2024 / BP 2025 (Trihexyphenidyl Hydrochloride BP 2024 / BP 2025)" if index % 3 == 0 else "BP 2025") for index in range(1, 21)]),
    "long-5": ("LONG-IFB-" + "X" * 71, [f"Product {index:03d} " + "pharmaceutical specification and alternative official description " * 3 for index in range(1, 6)]),
    "maximum-100": ("TEST-IFB", [f"Sample Product {index:03d}" for index in range(1, 101)]),
}


def create():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for stem, (ifb, names) in CASES.items():
        (OUTPUT / (stem + ".docx")).write_bytes(labels_document(ifb, names))
    # Earlier saved formats must remain identical.
    original = ROOT / ".tools/upgrade-audit-bdea782a/isolated/samples/SAMPLE-IFB_Sample_labels.docx"
    historical = labels_document("SAMPLE-IFB", ["Sample Product A", "Sample Product B", "Sample Product C"], layout_version=1)
    if original.is_file():
        assert historical == original.read_bytes(), "Historical layout changed"
    else:
        print("Historical installed layout-1 artifact unavailable; source compatibility tests still apply.")
    joined = ROOT / ".tools/upgrade-audit-bddda2bc/isolated/samples/SAMPLE-IFB_Sample_labels.docx"
    if joined.is_file():
        assert labels_document("SAMPLE-IFB", ["Sample Product A", "Sample Product B", "Sample Product C"], layout_version=2) == joined.read_bytes(), "Joined layout history changed"
    else:
        print("Historical installed layout-2 artifact unavailable; source compatibility tests still apply.")
    print("Original layout SHA256:", hashlib.sha256(historical).hexdigest())
    print("Specimens:", OUTPUT)


def validate_borders(page, expected_pairs):
    """Require independent closed rectangles, not shared table grid lines."""
    horizontal = [edge for edge in page.edges if edge["orientation"] == "h" and 270 < edge["x1"] - edge["x0"] < 280]
    vertical = [edge for edge in page.edges if edge["orientation"] == "v"]
    assert len(horizontal) == len(vertical) == expected_pairs * 4, "Each label needs four separate border segments"
    for right_column in (False, True):
        borders = sorted([edge for edge in horizontal if (edge["x0"] > 305) == right_column], key=lambda edge: edge["top"])
        assert len(borders) == expected_pairs * 2
        previous_bottom = None
        for top, bottom in zip(borders[::2], borders[1::2]):
            assert bottom["top"] - top["top"] > 25, "Collapsed label box"
            if previous_bottom is not None:
                assert top["top"] - previous_bottom >= 4.8, "Missing blank gap between labels"
            previous_bottom = bottom["top"]
            for side_x in (top["x0"], top["x1"]):
                assert any(abs(edge["x0"] - side_x) < 1.1 and abs(edge["top"] - top["top"]) < 1.1 and abs(edge["bottom"] - bottom["top"]) < 1.1 for edge in vertical), "Open label border"


def validate():
    import pdfplumber
    report = {}
    for stem, (_, names) in CASES.items():
        with pdfplumber.open(OUTPUT / (stem + "-render") / (stem + ".pdf")) as document:
            words_by_page = [page.extract_words() for page in document.pages]
            text = "\n".join(page.extract_text() or "" for page in document.pages)
            assert text.count("IFB NO :") == len(names) * 2, (stem, "Missing IFB numbers")
            for index in range(1, len(names) + 1):
                assert text.count(f"Product {index:03d}") == 2, (stem, index, "Missing/duplicate labels")
            for page, words in zip(document.pages, words_by_page):
                assert words, (stem, "Blank page")
                assert all(23 <= word["x0"] < word["x1"] <= 589 and
                           23 <= word["top"] < word["bottom"] <= 769 for word in words), (stem, "Text outside printable area")
                # Every pair starts and ends on the same page.
                page_text = page.extract_text() or ""
                assert page_text.count("IFB NO :") == sum(page_text.count(f"Product {index:03d}") for index in range(1, len(names) + 1)), (stem, "IFB separated from product")
                for index in range(1, len(names) + 1):
                    assert page_text.count(f"Product {index:03d}") in (0, 2), (stem, "Pair split")
                pairs = sum(f"Product {index:03d}" in page_text for index in range(1, len(names) + 1))
                validate_borders(page, pairs)
            if stem == "short-16":
                assert len(document.pages) == 1, "16 short products must fit on one sheet"
            report[stem] = {"pages": len(document.pages), "products": len(names), "labels": len(names) * 2,
                           "separate_four_border_boxes": "passed",
                           "pairs_per_page": [sum(f"Product {index:03d}" in (page.extract_text() or "") for index in range(1, len(names) + 1)) for page in document.pages]}
    (OUTPUT / "layout-checks.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    validate() if args.validate else create()
