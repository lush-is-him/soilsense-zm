"""Load and validate the rule tables in rules/*.yaml (spec 3, 6, NFR7)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

STATUSES = {"draft", "agronomist_input", "verified"}
SOURCE_TYPES = {"published", "expert_opinion", "derived", "proposed"}
PH_METHODS = {"water", "cacl2", "unconfirmed"}
REQUIRED_KEYS = ("id", "domain", "status", "source_type", "source_doc", "reviewer_alias", "data")
PH_DOMAINS = {"ph_band", "crop"}       # every rule in these must state its pH method
MARKERS = ("OPEN", "CONFLICT")
# Reviewers who have said they will not confirm the tables (spec 3).
NON_CONFIRMING_REVIEWERS = {"AGR-1"}

DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


class RuleError(ValueError):
    """The rule tables are invalid; the message lists every problem."""


@dataclass
class Rule:
    id: str
    domain: str
    status: str
    source_type: str
    source_doc: Optional[str]
    reviewer_alias: Optional[str]
    data: dict
    ref: Optional[str] = None
    ph_method: Optional[str] = None
    notes: Optional[str] = None
    file: Optional[str] = None

    def summary(self):
        return {"id": self.id, "status": self.status, "source_type": self.source_type,
                "reviewer_alias": self.reviewer_alias}


@dataclass
class RuleSet:
    rules: dict
    open_items: list = field(default_factory=list)

    def __getitem__(self, rule_id):
        return self.rules[rule_id]

    def by_domain(self, domain):
        return [r for r in self.rules.values() if r.domain == domain]

    def crop(self, name):
        for rule in self.by_domain("crop"):
            if rule.data.get("name") == name:
                return rule
        return None


def _find_markers(value, path=""):
    """Yield (path, marker) for every OPEN or CONFLICT value inside `value`."""
    if isinstance(value, str) and value in MARKERS:
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _find_markers(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _find_markers(item, f"{path}[{i}]")


def validate_entry(entry, file_name=""):
    """Return a list of problems with one rule entry."""
    where = f"{file_name}: {entry.get('id', '<no id>')}"
    problems = [f"{where}: missing '{key}'" for key in REQUIRED_KEYS if key not in entry]
    if problems:
        return problems
    if entry["status"] not in STATUSES:
        problems.append(f"{where}: status '{entry['status']}' not one of {sorted(STATUSES)}")
    if entry["source_type"] not in SOURCE_TYPES:
        problems.append(f"{where}: source_type '{entry['source_type']}' not one of {sorted(SOURCE_TYPES)}")
    method = entry.get("ph_method")
    if method is not None and method not in PH_METHODS:
        problems.append(f"{where}: ph_method '{method}' not one of {sorted(PH_METHODS)}")
    if entry["domain"] in PH_DOMAINS and method is None:
        problems.append(f"{where}: pH-dependent rule must state ph_method")
    if entry["status"] == "verified":
        published = entry["source_type"] == "published" and entry["source_doc"]
        confirmed = entry["reviewer_alias"] and entry["reviewer_alias"] not in NON_CONFIRMING_REVIEWERS
        if not (published or confirmed):
            problems.append(f"{where}: cannot be 'verified' without a cited published source "
                            f"or a confirming reviewer (AGR-1 does not confirm)")
    return problems


def load(rules_dir=DEFAULT_RULES_DIR):
    """Load every rules/*.yaml file. Raises RuleError if any rule is invalid."""
    rules, problems, open_items = {}, [], []
    for path in sorted(Path(rules_dir).glob("*.yaml")):
        content = yaml.safe_load(path.read_text()) or {}
        for entry in content.get("rules", []):
            problems += validate_entry(entry, path.name)
            rule_id = entry.get("id")
            if rule_id in rules:
                problems.append(f"{path.name}: duplicate rule id {rule_id}")
            if problems or rule_id is None:
                continue
            rules[rule_id] = Rule(
                id=rule_id, domain=entry["domain"], status=entry["status"],
                source_type=entry["source_type"], source_doc=entry["source_doc"],
                reviewer_alias=entry["reviewer_alias"], data=entry["data"] or {},
                ref=entry.get("ref"), ph_method=entry.get("ph_method"),
                notes=entry.get("notes"), file=path.name)
            open_items += [{"rule": rule_id, "path": p, "marker": m}
                           for p, m in _find_markers(entry["data"])]
    if problems:
        raise RuleError("invalid rule tables:\n  " + "\n  ".join(problems))
    return RuleSet(rules, open_items)
