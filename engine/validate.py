"""Check the rule tables and list every OPEN and CONFLICT value.

    python -m engine.validate [rules_dir]
"""

import sys
from collections import Counter

from .ruleset import DEFAULT_RULES_DIR, RuleError, load


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rules_dir = argv[0] if argv else DEFAULT_RULES_DIR
    try:
        ruleset = load(rules_dir)
    except RuleError as error:
        print(error)
        return 1
    statuses = Counter(rule.status for rule in ruleset.rules.values())
    print(f"{len(ruleset.rules)} rules valid: "
          + ", ".join(f"{n} {s}" for s, n in sorted(statuses.items())))
    print(f"\n{len(ruleset.open_items)} values not yet supplied:")
    for item in ruleset.open_items:
        print(f"  {item['marker']:8} {item['rule']:16} {item['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
