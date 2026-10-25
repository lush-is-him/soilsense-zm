# OPTIONAL: draws a map of your 486 SoilGrids points coloured by pH.
# Run on your laptop:  python make_kafue_map.py
# Then upload kafue_ph_map.png into the Overleaf "figures" folder
# (see README.txt for the lines to paste into main.tex).
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv(r"C:\Users\USER\SoilSense ZM\kafue_soil_data.csv")
fig, ax = plt.subplots(figsize=(7, 6))
sc = ax.scatter(df["longitude"], df["latitude"], c=df["pH"], cmap="RdYlGn",
                vmin=5.5, vmax=7.0, s=14, edgecolor="none")
cb = fig.colorbar(sc, ax=ax); cb.set_label("Modelled pH in water, 0-5 cm")
ax.set_xlabel("Longitude (degrees E)"); ax.set_ylabel("Latitude (degrees)")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig("kafue_ph_map.png", dpi=300)
print("Saved kafue_ph_map.png")
