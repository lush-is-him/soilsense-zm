# ============================================================
# SoilSense ZM — Phase 2.1
# generate_training_data.py
#
# Generates 2,000 synthetic soil samples mimicking real
# Kafue District conditions for ML model training.
#
# Author: Lushomo Sibalwa — 202301072 — ZCAS University
# ============================================================

import numpy as np
import pandas as pd
import os

np.random.seed(42)

OUTPUT_DIR = r"C:\Users\USER\SoilSense ZM"
CSV_OUTPUT = os.path.join(OUTPUT_DIR, "synthetic_training_data_v2.csv")

N_SAMPLES = 2000

print("=" * 55)
print("  SoilSense ZM — generate_training_data.py (v2 - 3 Features)")
print("=" * 55)

# ── DEFINE REALISTIC RANGES PER CLASS ─────────────────────────
# Based on Zambian soil science literature:
#   - Kafue District sits on Kalahari sands + alluvial soils
#   - pH typically ranges 4.2–7.2
#   - Acidic soils are common in high-rainfall areas
#   - Organic carbon varies with land use

classes = {
    "Healthy": {
        "n": 400,
        "pH":              (6.0, 7.5),
        "moisture":        (25, 45),
        "temperature":     (20, 30),
    },
    "Moderate": {
        "n": 600,
        "pH":              (5.5, 6.2),
        "moisture":        (18, 35),
        "temperature":     (22, 34),
    },
    "Degraded": {
        "n": 650,
        "pH":              (4.5, 5.6),
        "moisture":        (10, 25),
        "temperature":     (25, 38),
    },
    "Critical": {
        "n": 350,
        "pH":              (3.8, 4.8),
        "moisture":        (5, 18),
        "temperature":     (28, 42),
    },
}

# ── GENERATE DATA ─────────────────────────────────────────────
print("\n[1/3] Generating synthetic soil samples...")

all_rows = []

for label, params in classes.items():
    n = params["n"]
    print(f"   {label}: {n} samples")

    for _ in range(n):
        row = {"soil_health": label}

        for feature in ["pH", "moisture", "temperature"]:
            lo, hi = params[feature]
            mid = (lo + hi) / 2
            std = (hi - lo) / 4  # ~95% within range

            val = np.random.normal(mid, std)
            # Clamp to reasonable physical limits
            if feature == "pH":
                val = np.clip(val, 3.0, 9.0)
            elif feature == "moisture":
                val = np.clip(val, 0, 100)
            elif feature == "temperature":
                val = np.clip(val, 5, 55)

            row[feature] = round(val, 2)

        all_rows.append(row)

df = pd.DataFrame(all_rows)

# Shuffle the data
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# ── ADD NOISE FOR REALISM ─────────────────────────────────────
# Some overlap between classes is realistic — soil health is a spectrum
print("\n[2/3] Adding realistic noise (class boundary overlap)...")

# Add ~5% label noise to simulate real-world ambiguity
noise_indices = df.sample(frac=0.05, random_state=99).index
labels = list(classes.keys())
for idx in noise_indices:
    current = df.loc[idx, "soil_health"]
    # Shift to adjacent class
    pos = labels.index(current)
    if pos == 0:
        df.loc[idx, "soil_health"] = labels[1]
    elif pos == len(labels) - 1:
        df.loc[idx, "soil_health"] = labels[-2]
    else:
        df.loc[idx, "soil_health"] = labels[pos + np.random.choice([-1, 1])]

# ── SAVE CSV ──────────────────────────────────────────────────
print("\n[3/3] Saving CSV...")

# Reorder columns
col_order = ["pH", "moisture", "temperature", "soil_health"]
df = df[col_order]

df.to_csv(CSV_OUTPUT, index=False)

# ── SUMMARY ───────────────────────────────────────────────────
print(f"\n{'=' * 55}")
print("  SYNTHETIC TRAINING DATA SUMMARY")
print(f"{'=' * 55}")
print(f"\n  Total samples: {len(df)}")
print(f"  Features:      {len(col_order) - 1}")
print(f"  Target:        soil_health")
print(f"\n  Class distribution:")
for label, count in df["soil_health"].value_counts().sort_index().items():
    pct = count / len(df) * 100
    print(f"    {label:12s}: {count:4d} ({pct:.1f}%)")

print(f"\n  Feature ranges:")
for col in col_order[:-1]:
    print(f"    {col:16s}: {df[col].min():.2f} – {df[col].max():.2f}  (mean: {df[col].mean():.2f})")

print(f"\n  [OK] Saved: {CSV_OUTPUT}")
print(f"  Next step: run train_model.py")
print(f"{'=' * 55}\n")
