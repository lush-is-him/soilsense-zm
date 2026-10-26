"""Rule engine: Plans A, B and C from the rule tables (spec 2.1, 2.6, 6).

Every number used here comes from rules/*.yaml. The engine records which
rules fired so the advice can show "why this advice" (NFR1), and it never
fills in an OPEN or CONFLICT value: anything that depends on one comes back
as "lab test recommended" or "rate not yet available".
"""

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .config import DEFAULT_CONFIG
from .i18n import text
from .ruleset import RuleSet
from .trust import LOW, MODERATE, NONE

MONTHS = {name: i for i, name in enumerate(calendar.month_abbr) if name}
DAYS_PER_MONTH = 30.44
TEXTURE_GROUPS = ("sandy", "loamy", "clay")
# Texture may come from these sources; the map only counts when trust is Moderate.
TRUSTED_TEXTURE_SOURCES = {"field_check", "lab"}


@dataclass
class AdviceRequest:
    ph: float                         # probe mean, map value or lab value
    ph_method: str                    # "water" (probe, map) or "cacl2" (lab)
    trust_level: str
    crop: str
    as_of_date: date
    water: str = "rainfed"            # or "irrigated"
    budget_band: str = "low"
    texture: Optional[str] = None     # "sandy"/"loamy"/"clay" or a USDA class name
    texture_source: Optional[str] = None   # "field_check", "lab" or "map"
    lang: str = "en"


class Advisor:
    def __init__(self, rules: RuleSet, config=DEFAULT_CONFIG):
        self.rules = rules
        self.config = config

    # ----- public -------------------------------------------------------

    def advise(self, req: AdviceRequest):
        fired = []
        result = {
            "trust_level": req.trust_level,
            "crop": req.crop,
            "ph_input": req.ph,
            "ph_method_input": req.ph_method,
            "rules_ph_method": self.rules["BAND-01"].ph_method,
            "as_of_date": req.as_of_date.isoformat(),
            "refusals": [],
            "method_sensitive": False,
            "borderline": False,
            "plan_a": None,
            "plan_b": None,
            "plan_c": None,
            "alternatives": [],
            "messages": [],
        }

        if req.trust_level == NONE:
            fired.append("REF-01")
            result["refusals"] = ["REF-01"]
            return self._finish(result, fired, ["MSG-08"], req.lang)

        candidates = self._ph_in_rule_scale(req.ph, req.ph_method, result["rules_ph_method"])
        outcomes = [self._evaluate(ph, req) for ph in candidates]
        chosen = outcomes[0]

        if len({o["signature"] for o in outcomes}) > 1:
            # Spec 2.6: the plan depends on the unconfirmed pH method.
            result["method_sensitive"] = True
            for outcome in outcomes:
                fired += outcome["fired"]
            fired.append("REF-06")
            result["refusals"] = sorted({r for o in outcomes for r in o["refusals"]} | {"REF-06"})
            result["alternatives"] = [self._summary(o) for o in outcomes]
            result["plan_a"] = {"status": "lab_test_recommended", "note": "ref.REF-06"}
            crop_lists = [set(o["plan_c"]["crops"]) for o in outcomes]
            safe = [c for c in outcomes[0]["plan_c"]["crops"] if all(c in s for s in crop_lists)]
            result["plan_c"] = {"crops": safe, "note": None if safe else "plan.c_none",
                                "basis": "crops suitable under every pH interpretation"}
            messages = ["MSG-08"]
        else:
            fired += chosen["fired"]
            result["refusals"] = chosen["refusals"]
            result["plan_a"] = chosen["plan_a"]
            result["plan_c"] = chosen["plan_c"]
            messages = chosen["messages"] + ["MSG-08"]

        result["borderline"] = any(o["borderline"] for o in outcomes)
        fired += ["PLAN-B-BLOCKED", "LIME-PARTIAL"]
        result["plan_b"] = {"status": "blocked", "note": "plan.b_blocked"}
        return self._finish(result, fired, messages, req.lang)

    # ----- pH method (spec 2.6) ---------------------------------------

    def _ph_in_rule_scale(self, ph, input_method, rule_method):
        """The farmer's pH as it would read in the rules' method. First item is as-is."""
        low, high = self.config.PH_WATER_MINUS_CACL2
        if rule_method == input_method:
            return [ph]
        sign = -1 if input_method == "water" else 1     # water reads higher than CaCl2
        converted = [round(ph + sign * low, 2), round(ph + sign * high, 2)]
        if rule_method == "unconfirmed":
            return [ph] + converted
        return converted

    # ----- one interpretation ----------------------------------------

    def _evaluate(self, ph, req):
        fired, refusals, messages = ["BAND-01"], [], []
        band = self._band(ph)
        out = {"ph": ph, "band": band, "fired": fired, "refusals": refusals,
               "messages": messages, "plan_a": None,
               "plan_c": self._plan_c(ph, fired), "borderline": self._borderline(ph)}

        refuse_below = self.rules["REF-02"].data["refuse_below_ph"]
        if ph < refuse_below:
            fired.append("REF-02")
            refusals.append("REF-02")
            out["plan_c"] = {"crops": [], "note": "ref.REF-02"}
            return self._sign(out)

        crop_rule = self.rules.crop(req.crop)
        if crop_rule is None:
            raise ValueError(f"unknown crop {req.crop!r}")
        fired.append(crop_rule.id)
        crop = crop_rule.data
        if crop.get("in_scope") is not True:
            out["plan_a"] = {"status": "crop_not_confirmed", "note": "crop.pending_scope"}
            return self._sign(out)
        if crop.get("ph") == "OPEN":
            out["plan_a"] = {"status": "no_data", "note": "crop.no_data"}
            return self._sign(out)

        if ph > crop["ph"]["highest_workable"]:
            fired.append("REF-04")
            refusals.append("REF-04")
            out["plan_a"] = {"status": "ph_too_high", "note": "ref.REF-04"}
            return self._sign(out)

        fired.append("PLAN-A")
        lime = self._lime(band, req, crop, fired, refusals)
        fertiliser = self._fertiliser(crop)
        lima_ha = self._lima_ha(fired)
        out["plan_a"] = {
            "status": "ok",
            "lime": lime,
            "fertiliser": fertiliser,
            "manure": self._range_per_lima(crop["manure_t_ha"], lima_ha, "t"),
            "cautions": list(crop.get("cautions", [])),
            "measures_note": "measure.unavailable",
        }
        fired.append("MEAS-HOUSEHOLD")
        if lime.get("advised"):
            messages += ["MSG-01", "MSG-02", "MSG-03", "MSG-04"]
            fired += ["MSG-01", "MSG-02", "MSG-03", "MSG-04", "LIME-RESIDUAL"]
        messages += crop.get("cautions", [])
        fired += crop.get("cautions", [])
        messages.append("MSG-07")
        fired.append("MSG-07")
        return self._sign(out)

    # ----- pieces of Plan A --------------------------------------------

    def _band(self, ph):
        for band in self.rules["BAND-01"].data["bands"]:
            if "lt" in band and not ph < band["lt"]:
                continue
            if "lte" in band and not ph <= band["lte"]:
                continue
            if "gte" in band and not ph >= band["gte"]:
                continue
            if "gt" in band and not ph > band["gt"]:
                continue
            return band["id"]
        raise ValueError(f"pH {ph} matches no band")

    def _borderline(self, ph):
        edges = set()
        for band in self.rules["BAND-01"].data["bands"]:
            edges |= {band[k] for k in ("lt", "lte", "gte", "gt") if k in band}
        return any(abs(ph - edge) <= self.config.BORDERLINE_MARGIN for edge in edges)

    def _texture_group(self, req, fired):
        if req.texture is None:
            return None
        if req.texture_source not in TRUSTED_TEXTURE_SOURCES and not (
                req.texture_source == "map" and req.trust_level == MODERATE):
            return None
        if req.texture in TEXTURE_GROUPS:
            return req.texture
        fired.append("TEX-GROUPS")
        for group, classes in self.rules["TEX-GROUPS"].data["groups"].items():
            if req.texture in classes:
                return group
        return None

    def _lime(self, band, req, crop, fired, refusals):
        fired += ["LIME-TRIGGER", "LIME-TARGET"]
        if band == "suitable":
            return {"advised": False, "status": "not_needed", "note": "lime.not_needed"}
        # C-3: trigger OPEN; below 5.5 lime is advised, 5.5-6.5 is optional.
        status = "optional" if band == "slight" else "advised"
        lime = {"advised": True, "status": status,
                "note": "lime.optional" if status == "optional" else None,
                "products": self.rules["LIME-PRODUCTS"].data["products"],
                "target_ph": self.rules["LIME-TARGET"].data["target_ph"]}
        fired += ["LIME-PRODUCTS", "LIME-TEXTURE-REQUIRED"]

        group = self._texture_group(req, fired)
        if group is None:
            fired.append("REF-03")
            refusals.append("REF-03")
            lime.update(rate_t_ha=None, note="ref.REF-03")
        else:
            fired += ["LIME-RATES", "LIME-MAX"]
            low, high = self.rules["LIME-RATES"].data["rates_t_per_ha"][band][group]
            cap = self.rules["LIME-MAX"].data["max_single_application_t_ha"]
            if high > cap:
                fired.append("REF-07")
                refusals.append("REF-07")
                lime["split"] = True
            lime.update(texture_group=group, rate_t_ha=[low, min(high, cap)],
                        per_lima=self._range_per_lima([low, min(high, cap)],
                                                      self._lima_ha(fired), "kg", 1000))

        timing = self._timing(req, crop, fired)
        lime["timing"] = timing
        if timing == "too_late":
            fired.append("REF-05")
            refusals.append("REF-05")
            lime["this_season"] = False
        return lime

    def _timing(self, req, crop, fired):
        """REF-05: can lime still react before this crop's planting window?"""
        fired.append("LIME-LEAD-TIME")
        if req.water == "irrigated":
            return "any_time"
        lead = self.rules["LIME-LEAD-TIME"].data
        value = lead["lead_time_before_planting_months"]
        if isinstance(value, list):
            lead_min, lead_max = value
        else:   # CONFLICT: use the full range of the candidate answers (C-7)
            spans = list(lead["candidates_months"].values())
            lead_min, lead_max = min(s[0] for s in spans), max(s[1] for s in spans)
        start, end = self._next_window(crop["planting_window_rainfed"], req.as_of_date)
        to_start = max(0.0, (start - req.as_of_date).days / DAYS_PER_MONTH)
        to_end = (end - req.as_of_date).days / DAYS_PER_MONTH
        if to_end < lead_min:
            return "too_late"
        if to_start >= lead_max:
            return "ok"
        return "uncertain"

    @staticmethod
    def _next_window(window, as_of):
        """First and last day of the next planting window that has not ended."""
        start_m, end_m = MONTHS[window[0]], MONTHS[window[1]]
        for year in (as_of.year - 1, as_of.year, as_of.year + 1):
            start = date(year, start_m, 1)
            end_year = year if end_m >= start_m else year + 1
            end = date(end_year, end_m, calendar.monthrange(end_year, end_m)[1])
            if end >= as_of:
                return start, end
        raise AssertionError("unreachable")

    def _fertiliser(self, crop):
        def item(spec):
            rate = spec.get("rate_kg_ha")
            if rate in (None, "OPEN"):
                return {"product": spec.get("product"), "rate_kg_ha": None, "note": "rate.open"}
            return {"product": spec.get("product"), "rate_kg_ha": rate}
        return {"basal": item(crop["basal"]), "top_dress": item(crop["top_dress"])}

    def _lima_ha(self, fired):
        if "MEAS-LIMA" not in fired:
            fired.append("MEAS-LIMA")
        return self.rules["MEAS-LIMA"].data["lima_ha"]

    @staticmethod
    def _range_per_lima(per_ha, lima_ha, unit, factor=1):
        low, high = per_ha
        return {"low": round(low * lima_ha * factor, 2),
                "high": round(high * lima_ha * factor, 2), "unit": unit}

    # ----- Plan C ------------------------------------------------------

    def _plan_c(self, ph, fired):
        fired.append("PLAN-C-ORDER")
        first = self.rules["PLAN-C-ORDER"].data["first_preference"]
        suitable = []
        for rule in self.rules.by_domain("crop"):
            crop = rule.data
            if crop.get("in_scope") is not True or crop.get("ph") == "OPEN":
                continue
            if crop["ph"]["lowest_workable"] <= ph <= crop["ph"]["highest_workable"]:
                suitable.append((crop["name"] not in first, crop["ph"]["lowest_workable"],
                                 crop["name"]))
        crops = [name for *_, name in sorted(suitable)]
        return {"crops": crops, "note": None if crops else "plan.c_none"}

    # ----- helpers -----------------------------------------------------

    @staticmethod
    def _sign(out):
        plan_a = out["plan_a"] or {}
        lime = plan_a.get("lime") or {}
        out["signature"] = (
            tuple(sorted(out["refusals"])), out["band"], plan_a.get("status"),
            lime.get("status"), tuple(lime.get("rate_t_ha") or ()), lime.get("timing"),
            tuple(out["plan_c"]["crops"]))
        return out

    @staticmethod
    def _summary(outcome):
        plan_a = outcome["plan_a"] or {}
        lime = plan_a.get("lime") or {}
        return {"ph_in_rule_scale": outcome["ph"], "band": outcome["band"],
                "refusals": outcome["refusals"], "lime_status": lime.get("status"),
                "lime_rate_t_ha": lime.get("rate_t_ha"),
                "plan_c": outcome["plan_c"]["crops"]}

    def _finish(self, result, fired, messages, lang):
        seen = []
        for rule_id in fired + list(messages):
            if rule_id not in seen:
                seen.append(rule_id)
        result["fired_rules"] = [self.rules[r].summary() for r in seen]
        result["unreviewed"] = any(r["status"] != "verified" for r in result["fired_rules"])
        result["messages"] = [text(f"msg.{m}", lang) for m in dict.fromkeys(messages)]
        crop = result["crop"]
        result["refusal_text"] = [text(f"ref.{r}", lang, crop=crop) for r in result["refusals"]]
        if result["trust_level"] in (MODERATE, LOW):
            result["trust_text"] = text(f"trust.{result['trust_level']}", lang)
        return result
