"""Move probe readings saved under the wrong sample code (e.g. S06 was measured as S09).

    python scripts/move_sample.py S09 S06

Copies probe_ph_1..3 and probe_temp_c from the first sample to the second in
docs/evaluation/samples.csv and clears them on the first.
"""

import csv
import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "evaluation" / "samples.csv"
COLUMNS = ["probe_ph_1", "probe_ph_2", "probe_ph_3", "probe_temp_c"]


def move(wrong, right, path=SAMPLES):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    by_id = {r["sample_id"]: r for r in rows}
    for code in (wrong, right):
        if code not in by_id:
            raise SystemExit(f"ERROR: {code} is not in {path.name}")
    if not by_id[wrong]["probe_ph_1"]:
        raise SystemExit(f"ERROR: {wrong} has no probe reading to move")
    for col in COLUMNS:
        by_id[right][col], by_id[wrong][col] = by_id[wrong][col], ""
    note = f"probe reading taken under {wrong} by mistake, moved"
    by_id[right]["notes"] = f"{by_id[right]['notes']}; {note}".strip("; ")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Moved the probe reading from {wrong} to {right}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    move(sys.argv[1].upper(), sys.argv[2].upper())
