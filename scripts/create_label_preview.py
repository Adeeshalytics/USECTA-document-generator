"""Generate label specimens for print-layout QA without company-workspace writes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sample_labels import labels_document

SAMPLE_NAMES = ["Mefanamic Acid BP 2024 / BP 2025", "Hypromellose 2910 USP 47 / USP 48",
    "Benzhexol Hydrochloride BP 2024 / BP 2025 (Trihexyphenidyl Hydrochloride BP 2024 / BP 2025)"]


def main():
    output = ROOT / ".tools" / "tmp" / "labels-qa"
    output.mkdir(parents=True, exist_ok=True)
    (output / "reference-recreated.docx").write_bytes(labels_document("SPMC/02/2026", SAMPLE_NAMES))
    (output / "changed-fields.docx").write_bytes(labels_document("SPMC/03/2026", ["Sample Product A BP", "Sample Product B USP", "Sample Product C BP"]))
    (output / "multi-page-long.docx").write_bytes(labels_document("TEST-LABELS-2026", SAMPLE_NAMES +
        ["Sample product with a long pharmaceutical specification and alternative official description " * 2, "Fifth sample product", "Sixth sample product", "Seventh sample product"]))
    print("Label layout specimens:", output)


if __name__ == "__main__":
    main()
