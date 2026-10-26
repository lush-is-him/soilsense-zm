"""Mirror rules/*.yaml into the rules table and bump versions on change (spec 3)."""

import hashlib
import json

from engine.ruleset import load


def sync_rules(conn, rules_dir=None):
    ruleset = load(rules_dir) if rules_dir else load()
    with conn:
        for rule in ruleset.rules.values():
            body = json.dumps({"data": rule.data, "status": rule.status,
                               "source_type": rule.source_type, "source_doc": rule.source_doc,
                               "reviewer_alias": rule.reviewer_alias,
                               "ph_method": rule.ph_method}, sort_keys=True)
            digest = hashlib.sha256(body.encode()).hexdigest()
            row = conn.execute("SELECT version, content_hash FROM rules WHERE rule_id = ?",
                               (rule.id,)).fetchone()
            values = (rule.domain, json.dumps(rule.data), rule.status, rule.source_type,
                      rule.source_doc, rule.reviewer_alias, rule.ph_method, rule.notes)
            if row is None:
                conn.execute(
                    "INSERT INTO rules (rule_id, version, content_hash, domain, data, status, "
                    "source_type, source_doc, reviewer_alias, ph_method, notes) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (rule.id, digest, *values))
            elif row["content_hash"] != digest:
                conn.execute(
                    "UPDATE rules SET version = version + 1, content_hash = ?, domain = ?, "
                    "data = ?, status = ?, source_type = ?, source_doc = ?, reviewer_alias = ?, "
                    "ph_method = ?, notes = ?, updated_at = datetime('now') WHERE rule_id = ?",
                    (digest, *values, rule.id))
    return ruleset
