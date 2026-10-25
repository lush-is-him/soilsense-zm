# ============================================================
# SoilSense ZM — Phase 2.2–2.5
# train_model.py
#
# Loads synthetic training data, performs EDA, trains a
# Random Forest Classifier, evaluates, and saves the model.
#
# Author: Lushomo Sibalwa — 202301072 — ZCAS University
# ============================================================

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving plots
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report,
    confusion_matrix, ConfusionMatrixDisplay
)
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings('ignore')

# ── PATHS ────────────────────────────────────────────────────
BASE_DIR = r"C:\Users\USER\SoilSense ZM"
CSV_INPUT = os.path.join(BASE_DIR, "synthetic_training_data_v2.csv")
MODEL_OUTPUT = os.path.join(BASE_DIR, "soil_model_v2.pkl")
ENCODER_OUTPUT = os.path.join(BASE_DIR, "label_encoder_v2.pkl")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")

os.makedirs(PLOTS_DIR, exist_ok=True)

print("=" * 55)
print("  SoilSense ZM — train_model.py (v2 - 3 Features)")
print("=" * 55)

# ── STEP 1: LOAD DATA ────────────────────────────────────────
print("\n[1/5] Loading training data...")
df = pd.read_csv(CSV_INPUT)
print(f"   ✅ Loaded {len(df)} samples, {len(df.columns)} columns")
print(f"   Columns: {list(df.columns)}")

features = ["pH", "moisture", "temperature"]
target = "soil_health"

X = df[features]
y = df[target]

# Encode labels
le = LabelEncoder()
y_encoded = le.fit_transform(y)
class_names = le.classes_
print(f"   Classes: {list(class_names)}")

# ── STEP 2: EXPLORATORY DATA ANALYSIS ────────────────────────
print("\n[2/5] Exploratory Data Analysis — generating plots...")

# 2a. Feature distributions by class
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes = axes.flatten()  # Ensure axes is always a flat array
fig.suptitle("SoilSense ZM — Feature Distributions by Soil Health Class",
             fontsize=14, fontweight='bold')

colors = {"Critical": "#C1121F", "Degraded": "#E9C46A",
          "Moderate": "#90BE6D", "Healthy": "#2D6A4F"}

for idx, feature in enumerate(features):
    ax = axes[idx]
    for label in class_names:
        subset = df[df[target] == label][feature]
        ax.hist(subset, bins=25, alpha=0.5, label=label, color=colors.get(label, 'gray'))
    ax.set_title(feature, fontsize=11)
    ax.set_xlabel(feature)
    ax.set_ylabel("Count")
    ax.legend(fontsize=7)

plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "feature_distributions.png"), dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ Saved: plots/feature_distributions.png")

# 2b. Correlation matrix
fig, ax = plt.subplots(figsize=(8, 6))
corr = df[features].corr()
sns.heatmap(corr, annot=True, cmap="RdYlGn", center=0, fmt=".2f",
            square=True, ax=ax, linewidths=0.5)
ax.set_title("SoilSense ZM — Feature Correlation Matrix", fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "correlation_matrix.png"), dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ Saved: plots/correlation_matrix.png")

# 2c. Class distribution
fig, ax = plt.subplots(figsize=(8, 5))
counts = df[target].value_counts().reindex(class_names)
bars = ax.bar(counts.index, counts.values,
              color=[colors.get(c, 'gray') for c in counts.index],
              edgecolor='white', linewidth=1.5)
for bar, val in zip(bars, counts.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
            str(val), ha='center', fontweight='bold')
ax.set_title("SoilSense ZM — Training Data Class Distribution", fontsize=12, fontweight='bold')
ax.set_ylabel("Number of Samples")
ax.set_xlabel("Soil Health Class")
plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "class_distribution.png"), dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ Saved: plots/class_distribution.png")

# ── STEP 3: TRAIN/TEST SPLIT ─────────────────────────────────
print("\n[3/5] Splitting data (80/20, stratified)...")

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)
print(f"   Train: {len(X_train)} samples")
print(f"   Test:  {len(X_test)} samples")

# ── STEP 4: TRAIN RANDOM FOREST ──────────────────────────────
print("\n[4/5] Training Random Forest Classifier...")

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1,
    class_weight='balanced'
)

model.fit(X_train, y_train)
print("   ✅ Model trained successfully")

# ── STEP 5: EVALUATE ─────────────────────────────────────────
print("\n[5/5] Evaluating model...")

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred, average='weighted')

print(f"\n{'=' * 55}")
print("  MODEL EVALUATION RESULTS")
print(f"{'=' * 55}")
print(f"\n  Accuracy:          {accuracy:.4f} ({accuracy*100:.1f}%)")
print(f"  F1 Score (weighted): {f1:.4f}")

print(f"\n  Classification Report:")
report = classification_report(y_test, y_pred, target_names=class_names)
print(report)

# 5a. Confusion Matrix
fig, ax = plt.subplots(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
disp.plot(ax=ax, cmap="Greens", values_format="d")
ax.set_title("SoilSense ZM — Confusion Matrix", fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "confusion_matrix.png"), dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ Saved: plots/confusion_matrix.png")

# 5b. Feature Importance
fig, ax = plt.subplots(figsize=(8, 5))
importances = model.feature_importances_
indices = np.argsort(importances)[::-1]
feature_names_sorted = [features[i] for i in indices]
importance_values = importances[indices]

bars = ax.barh(range(len(features)), importance_values[::-1],
               color='#2D6A4F', edgecolor='white', linewidth=1)
ax.set_yticks(range(len(features)))
ax.set_yticklabels(feature_names_sorted[::-1])
ax.set_xlabel("Importance")
ax.set_title("SoilSense ZM — Feature Importance (Random Forest)", fontsize=12, fontweight='bold')

for i, (val, name) in enumerate(zip(importance_values[::-1], feature_names_sorted[::-1])):
    ax.text(val + 0.005, i, f"{val:.3f}", va='center', fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(PLOTS_DIR, "feature_importance.png"), dpi=150, bbox_inches='tight')
plt.close()
print("   ✅ Saved: plots/feature_importance.png")

# ── SAVE MODEL ────────────────────────────────────────────────
joblib.dump(model, MODEL_OUTPUT)
joblib.dump(le, ENCODER_OUTPUT)
print(f"\n  ✅ Model saved: soil_model_v2.pkl")
print(f"  ✅ Label encoder saved: label_encoder_v2.pkl")

# ── QUICK DEMO PREDICTION ────────────────────────────────────
print(f"\n{'=' * 55}")
print("  DEMO PREDICTION")
print(f"{'=' * 55}")

demo_inputs = [
    {"pH": 6.8, "moisture": 35, "temperature": 25},
    {"pH": 5.0, "moisture": 15, "temperature": 32},
    {"pH": 4.2, "moisture": 8, "temperature": 38},
]

for i, inp in enumerate(demo_inputs, 1):
    X_demo = pd.DataFrame([inp])
    pred_encoded = model.predict(X_demo)[0]
    pred_label = le.inverse_transform([pred_encoded])[0]
    proba = model.predict_proba(X_demo)[0]
    confidence = max(proba) * 100

    print(f"\n  Sample {i}: pH={inp['pH']}, moisture={inp['moisture']}%, temp={inp['temperature']}°C")
    print(f"  → Prediction: {pred_label} (confidence: {confidence:.1f}%)")

print(f"\n{'=' * 55}")
print("  ✅ PHASE 2 COMPLETE")
print(f"{'=' * 55}")
print(f"\n  Files created:")
print(f"  🤖 soil_model_v2.pkl         — trained Random Forest model (3 features)")
print(f"  🏷️  label_encoder_v2.pkl      — label encoder for classes")
print(f"  📊 plots/feature_distributions.png")
print(f"  📊 plots/correlation_matrix.png")
print(f"  📊 plots/class_distribution.png")
print(f"  📊 plots/confusion_matrix.png")
print(f"  📊 plots/feature_importance.png")
print(f"\n  Next step: start the FastAPI backend (Phase 3)")
print(f"{'=' * 55}\n")
