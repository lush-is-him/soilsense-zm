"""System Usability Scale scores from docs/evaluation/sus.csv (Brooke, 1996).

    python scripts/sus.py [docs/evaluation/sus.csv]

Odd items score (answer - 1), even items (5 - answer); the sum times 2.5
gives 0 to 100. Bangor, Kortum and Miller (2008) report a mean of about 70
across many studies, which the dissertation uses as the reference.
"""

import csv
import statistics
import sys

REFERENCE_MEAN = 70


def sus_score(answers):
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs ten answers from 1 to 5")
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))
    return total * 2.5


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else "docs/evaluation/sus.csv"
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    scores = []
    for row in rows:
        try:
            answers = [int(row[f"q{i}"]) for i in range(1, 11)]
        except (KeyError, ValueError):
            print(f"Skipping {row.get('participant')}: incomplete answers")
            continue
        score = sus_score(answers)
        scores.append((row, score))
        print(f"  {row['participant']:6} {row.get('role', ''):10} {score:5.1f}")
    if not scores:
        print(f"No complete SUS forms yet in {path}.")
        return 1
    values = [s for _, s in scores]
    spread = f", SD {statistics.stdev(values):.1f}" if len(values) > 1 else ""
    print(f"\nn = {len(values)}, mean SUS {statistics.mean(values):.1f}{spread}, "
          f"range {min(values):.1f} to {max(values):.1f} (reference mean about {REFERENCE_MEAN}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
