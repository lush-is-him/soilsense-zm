# Makes Figure 1.2 and Figure 2.1. Run on your laptop:  python make_charts.py
# Needs: pip install matplotlib pandas
# Figure 1.2 is built from your own CSV, so the counts come straight from your data.
import pandas as pd
import matplotlib.pyplot as plt

# ---------- Figure 1.2: pH distribution from your CSV ----------
df = pd.read_csv(r"C:\Users\USER\SoilSense ZM\kafue_soil_data.csv")
labels = ["< 5.5", "5.5-5.9", "6.0-6.4", "6.5-6.9", ">= 7.0"]
counts = [
    (df["pH"] < 5.5).sum(),
    ((df["pH"] >= 5.5) & (df["pH"] < 6.0)).sum(),
    ((df["pH"] >= 6.0) & (df["pH"] < 6.5)).sum(),
    ((df["pH"] >= 6.5) & (df["pH"] < 7.0)).sum(),
    (df["pH"] >= 7.0).sum(),
]
print("Counts per band:", dict(zip(labels, counts)))   # check these match Table 1.2
n = len(df)
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(labels, counts, color="grey", edgecolor="black")
for b, c in zip(bars, counts):
    ax.text(b.get_x() + b.get_width() / 2, c + 5, f"{c} ({c/n*100:.1f}%)", ha="center")
ax.set_xlabel("Modelled soil pH in water, 0-5 cm (SoilGrids 2.0)")
ax.set_ylabel(f"Number of points (n = {n})")
fig.tight_layout()
fig.savefig("fig1_2_kafue_ph_distribution.png", dpi=200)

# ---------- Figure 2.1: positioning of approaches ----------
pts = {
    "Laboratory testing": (0.93, 0.32),
    "Digital soil maps": (0.12, 0.12),
    "SoilDoc kit": (0.80, 0.55),
    "IoT platform (Oliveira-Jr et al.)": (0.70, 0.16),
    "iSDA Virtual Agronomist": (0.22, 0.80),
    "SoilSense ZM": (0.82, 0.87),
}
fig, ax = plt.subplots(figsize=(7, 5))
for name, (x, y) in pts.items():
    ax.scatter(x, y, color="black", marker="*" if name == "SoilSense ZM" else "o", s=120)
    ax.annotate(name, (x, y), xytext=(6, 6), textcoords="offset points", fontsize=9)
ax.set_xlim(0, 1.1); ax.set_ylim(0, 1.05)
ax.set_xticks([0.05, 0.95]); ax.set_xticklabels(["Modelled", "Measured on farm"])
ax.set_yticks([0.05, 0.95]); ax.set_yticklabels(["Data only", "Actionable plan"])
ax.set_xlabel("Where the soil information comes from")
ax.set_ylabel("What the farmer receives")
ax.axhline(0.5, color="grey", ls="--", lw=0.8); ax.axvline(0.5, color="grey", ls="--", lw=0.8)
fig.tight_layout()
fig.savefig("fig2_1_positioning.png", dpi=200)
print("Saved fig1_2_kafue_ph_distribution.png and fig2_1_positioning.png")
