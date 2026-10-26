"""Score the reviewer's scenario sheet for RQ3 (target: 80% agreement).

    python scripts/score_review.py [docs/scenarios/scenarios.csv]

The reviewer fills `agronomist_agrees` with yes, no or partial (partial
counts as half) and may add a recommendation and comment.
"""

import csv
import sys
from collections import defaultdict

TARGET = 0.80
SCORES = {"yes": 1.0, "y": 1.0, "agree": 1.0, "partial": 0.5, "no": 0.0, "n": 0.0, "disagree": 0.0}


def score(rows):
    answered, by_note, disagreements = [], defaultdict(list), []
    for row in rows:
        answer = (row.get("agronomist_agrees") or "").strip().lower()
        if not answer:
            continue
        if answer not in SCORES:
            raise SystemExit(f"{row['id']}: agronomist_agrees must be yes, no or partial, not {answer!r}")
        value = SCORES[answer]
        answered.append(value)
        by_note[row.get("note") or ""].append(value)
        if value < 1:
            disagreements.append(row)
    return answered, by_note, disagreements


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else "docs/scenarios/scenarios.csv"
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    answered, by_note, disagreements = score(rows)
    if not answered:
        print(f"No reviewed scenarios yet in {path} (fill the agronomist_agrees column).")
        return 1
    rate = sum(answered) / len(answered)
    print(f"Reviewed {len(answered)} of {len(rows)} scenarios. Agreement: {rate:.0%} "
          f"({'meets' if rate >= TARGET else 'does not meet'} the {TARGET:.0%} target).")
    print("\nBy scenario type:")
    for note, values in sorted(by_note.items()):
        print(f"  {note or '(none)':30} {sum(values) / len(values):.0%} of {len(values)}")
    if disagreements:
        print("\nNot full agreement:")
        for row in disagreements:
            print(f"  {row['id']} pH {row['ph']} {row['crop']} ({row['note']}): "
                  f"{row['agronomist_agrees']}. {row.get('agronomist_comment', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
