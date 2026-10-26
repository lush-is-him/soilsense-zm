"""GET /rules for agronomists and admins (FR14). Rules are edited in rules/*.yaml."""

import json

from fastapi import APIRouter, Depends

from backend.auth import require_role
from backend.db import get_db
from backend.services.rules_sync import sync_rules

router = APIRouter(tags=["Rules"], dependencies=[Depends(require_role("agronomist", "admin"))])


@router.get("/rules")
def list_rules(db=Depends(get_db)):
    ruleset = sync_rules(db)
    rows = [dict(r, data=json.loads(r["data"])) for r in db.execute("SELECT * FROM rules ORDER BY rule_id")]
    return {"rules": rows, "open_items": ruleset.open_items}
