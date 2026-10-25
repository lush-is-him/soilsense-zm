# ============================================================
# SoilSense ZM — Backend
# advisory.py — Zambia-specific soil health advisory engine
#
# Returns crop recommendations, lime/fertilizer rates, and
# management advice based on predicted soil health label.
# ============================================================


def get_advisory(soil_health: str, pH: float = None, moisture: float = None) -> dict:
    """
    Generate Zambia-specific advisory based on soil health prediction.

    Args:
        soil_health: One of "Healthy", "Moderate", "Degraded", "Critical"
        pH: Actual pH value for fine-tuned lime recommendation
        moisture: Actual moisture for irrigation advice

    Returns:
        dict with summary, recommendations, crop suitability, management advice, alert level
    """

    advisories = {
        "Healthy": {
            "summary": (
                "Your soil is in good health. Nutrient levels and pH are within the "
                "optimal range for most crops grown in Kafue District. Continue current "
                "management practices and monitor seasonally."
            ),
            "lime_recommendation": (
                "No liming required. Soil pH is within the optimal range (6.0–7.5). "
                "Re-test at the start of each growing season."
            ),
            "fertilizer_recommendation": (
                "Apply basal dressing of Compound D (10-20-10) at 200 kg/ha at planting. "
                "Top-dress with Urea (46-0-0) at 200 kg/ha 4–6 weeks after emergence. "
                "Consider organic manure (2–3 tonnes/ha) to maintain organic carbon levels."
            ),
            "crop_suitability": [
                "Maize (optimal — expected yield 5–8 tonnes/ha)",
                "Soybeans (excellent)",
                "Groundnuts (excellent)",
                "Sunflower (good)",
                "Wheat (good — if irrigated)",
                "Vegetables (tomatoes, rape, cabbage)"
            ],
            "management_advice": [
                "Maintain crop rotation: maize → legume → maize",
                "Incorporate crop residues after harvest to sustain organic matter",
                "Apply 2–3 tonnes/ha of compost or cattle manure annually",
                "Practice minimum tillage to preserve soil structure",
                "Monitor soil moisture — irrigate if below 25% during dry spells"
            ],
            "alert_level": "green"
        },

        "Moderate": {
            "summary": (
                "Your soil shows early signs of nutrient depletion. pH is slightly below "
                "optimal and some nutrient levels are declining. Corrective action now will "
                "prevent further degradation and maintain crop yields."
            ),
            "lime_recommendation": (
                "Apply agricultural lime at 1–2 tonnes/ha to raise pH above 5.8. "
                "Use dolomitic lime if magnesium deficiency is suspected. "
                "Apply 2–3 months before planting for best results. "
                "Re-test after one growing season."
            ),
            "fertilizer_recommendation": (
                "Apply Compound D (10-20-10) at 200 kg/ha as basal dressing. "
                "Top-dress with Urea at 250 kg/ha in two splits (4 and 7 weeks after emergence). "
                "Add single superphosphate (SSP) at 100 kg/ha if phosphorus is low. "
                "Incorporate well-decomposed manure at 3–5 tonnes/ha."
            ),
            "crop_suitability": [
                "Maize (good — expected yield 3–5 tonnes/ha with amendments)",
                "Soybeans (good — will also fix nitrogen)",
                "Groundnuts (good)",
                "Cowpeas (recommended — nitrogen fixing, drought tolerant)",
                "Sweet potatoes (good — tolerant of moderate acidity)"
            ],
            "management_advice": [
                "Apply lime immediately — do not wait for next season",
                "Increase legume proportion in rotation to restore nitrogen",
                "Plant cover crops (velvet beans, sun hemp) during off-season",
                "Reduce tillage depth to protect remaining soil structure",
                "Add organic matter: crop residues, compost, or green manure",
                "Consider contour ridging to reduce nutrient runoff"
            ],
            "alert_level": "yellow"
        },

        "Degraded": {
            "summary": (
                "Your soil is degraded. pH is too low for optimal maize production and "
                "nutrient levels are significantly depleted. Without intervention, crop yields "
                "will continue to decline. Immediate corrective action is strongly recommended."
            ),
            "lime_recommendation": (
                "URGENT: Apply agricultural lime at 2–4 tonnes/ha. "
                "Dolomitic lime is preferred (provides both calcium and magnesium). "
                "Apply at least 3 months before planting season. "
                "May need repeat application next season. "
                "Contact your local agricultural extension officer for soil-specific rates."
            ),
            "fertilizer_recommendation": (
                "Apply Compound D at 200 kg/ha as basal dressing. "
                "Top-dress with Urea at 300 kg/ha in two splits. "
                "Add SSP at 150 kg/ha for phosphorus correction. "
                "Apply Muriate of Potash (MOP) at 50 kg/ha if potassium is low. "
                "CRITICAL: Apply 5+ tonnes/ha of well-decomposed cattle manure or compost."
            ),
            "crop_suitability": [
                "Maize (poor without liming — expect <2 tonnes/ha)",
                "Cassava (tolerant of acid soils — recommended as interim crop)",
                "Sweet potatoes (fair — more tolerant of low pH)",
                "Cowpeas (recommended — nitrogen fixing)",
                "Dry Beans/Mixed Beans (Zambian varieties like Solwezi beans, moderately acid tolerant)",
                "Soya Beans (nitrogen fixing, but requires inoculant & lime for good yields)",
                "Finger millet (tolerant of poor soils)",
                "AVOID: Wheat, highly sensitive vegetables until pH is corrected"
            ],
            "management_advice": [
                "PRIORITY 1: Apply lime before next planting",
                "PRIORITY 2: Add as much organic matter as possible",
                "Switch to acid-tolerant crops until soil pH recovers",
                "Plant nitrogen-fixing cover crops (velvet beans, Mucuna)",
                "Stop burning crop residues — incorporate them instead",
                "Reduce tillage to prevent further structure breakdown",
                "Build contour ridges or terraces to prevent erosion",
                "Consult ZCAS/UNZA extension services for a full soil assessment"
            ],
            "alert_level": "orange"
        },

        "Critical": {
            "summary": (
                "⚠️ CRITICAL: Your soil is severely degraded. pH is dangerously low and "
                "nutrient reserves are near-depleted. Growing maize on this soil without "
                "correction will result in crop failure. Immediate, aggressive rehabilitation "
                "is required. Contact your agricultural extension officer urgently."
            ),
            "lime_recommendation": (
                "EMERGENCY: Apply agricultural lime at 4–6 tonnes/ha immediately. "
                "Use dolomitic lime for combined calcium + magnesium correction. "
                "Apply in two doses: 3 tonnes/ha now, 3 tonnes/ha next season. "
                "Lime will take 2–3 months to take effect. "
                "pH must reach at least 5.5 before planting maize. "
                "Seek professional soil testing through ZARI or UNZA."
            ),
            "fertilizer_recommendation": (
                "Do NOT apply chemical fertilizer until lime has corrected pH — "
                "nutrients will be locked out at this pH level. "
                "Instead: Apply 8–10 tonnes/ha of well-decomposed organic manure. "
                "After liming (once pH > 5.0): Apply Compound D at 200 kg/ha + "
                "Urea at 250 kg/ha + SSP at 200 kg/ha. "
                "Consider foliar feeding as a short-term nutrient supplement."
            ),
            "crop_suitability": [
                "Cassava (BEST OPTION — highly tolerant of acid soils)",
                "Sweet potatoes (fair)",
                "Finger millet (tolerant)",
                "Pineapple (prefers acid soils pH 4.5–5.5)",
                "DO NOT plant: maize, soybeans, wheat, groundnuts, vegetables",
                "Consider a full-season fallow with cover crops for rehabilitation"
            ],
            "management_advice": [
                "🚨 STOP all maize planting until soil is rehabilitated",
                "Apply lime IMMEDIATELY — this is your #1 priority",
                "Switch entirely to acid-tolerant crops this season",
                "Maximize organic matter inputs (manure, compost, green manure)",
                "Plant cover crops: velvet beans, sun hemp, Mucuna pruriens",
                "Zero tillage only — any plowing will worsen degradation",
                "Build soil conservation structures (ridges, bunds)",
                "Contact the nearest agricultural camp or DACO office",
                "Consider government lime subsidy programs (FISP)",
                "Plan for 2–3 season rehabilitation before returning to maize"
            ],
            "alert_level": "red"
        }
    }

    advisory = advisories.get(soil_health, advisories["Moderate"])

    # Fine-tune lime recommendation based on actual pH
    if pH is not None:
        if pH >= 6.5:
            advisory["lime_recommendation"] = (
                "No liming needed. pH is at " + f"{pH:.1f}" + " which is optimal."
            )
        elif pH >= 5.5:
            advisory["lime_recommendation"] += (
                f"\n\nNote: Your actual pH is {pH:.1f}. Apply 1–2 tonnes/ha of lime."
            )
        elif pH >= 4.5:
            advisory["lime_recommendation"] += (
                f"\n\nNote: Your actual pH is {pH:.1f}. Apply 2–4 tonnes/ha of lime urgently."
            )
        else:
            advisory["lime_recommendation"] += (
                f"\n\n⚠️ Your actual pH is {pH:.1f}. Apply 4–6 tonnes/ha of lime IMMEDIATELY."
            )

    return advisory
