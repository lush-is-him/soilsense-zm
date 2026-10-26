"""Household measures and costs from rules/measures.yaml and rules/prices.yaml (FR11).

Both tables are OPEN until the developer weighs containers (H3) and collects
prices (H4). Until then these functions return None and the advice keeps
amounts in kg with a "household measure not yet available" note.
"""

MATERIALS = {"lime": "lime", "compound d": "compound_d", "urea": "urea", "manure": "manure"}


def material_for(product):
    """Map a product name from the rule tables to a measures/prices key."""
    name = (product or "").lower()
    for key, material in MATERIALS.items():
        if key in name:
            return material
    return None


def _round_half(value):
    return round(value * 2) / 2


def household(kg_low, kg_high, material, ruleset):
    """Express a kg range in containers whose weight is known for this material."""
    if material is None or kg_high is None:
        return None
    options = []
    for container in ruleset["MEAS-HOUSEHOLD"].data.get("containers") or []:
        per = (container.get("kg") or {}).get(material)
        if not isinstance(per, (int, float)) or per <= 0:
            continue
        low, high = _round_half(kg_low / per), _round_half(kg_high / per)
        if high < 0.5 or low > 40:          # too small or too many to be a useful measure
            continue
        options.append({"container": container["label"], "low": low, "high": high})
    return options or None


def cost(kg_low, kg_high, material, ruleset):
    """ZMW cost range for a kg range, or None if no price is recorded."""
    if material is None or kg_high is None or "PRICE-INPUTS" not in ruleset.rules:
        return None
    data = ruleset["PRICE-INPUTS"].data
    item = (data.get("items") or {}).get(material) or {}
    price = item.get("zmw_per_kg")
    if not isinstance(price, (int, float)):
        return None
    return {"low": round(kg_low * price), "high": round(kg_high * price),
            "currency": data.get("currency", "ZMW"), "place": item.get("place"), "date": item.get("date")}
