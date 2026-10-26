import pandas as pd
import rasterio

df = pd.read_csv(r"C:\Users\USER\SoilSense ZM\kafue_soil_data.csv")

print("Total rows:", len(df))
print(df["pH"].describe())

below_55 = (df["pH"] < 5.5).sum()
below_65 = (df["pH"] < 6.5).sum()
print(f"Below 5.5: {below_55} rows = {below_55/len(df)*100:.1f}%")
print(f"Below 6.5: {below_65} rows = {below_65/len(df)*100:.1f}%")

distinct = df[["longitude", "latitude"]].round(2).drop_duplicates().shape[0]
print("Distinct locations (rounded to 0.01 deg):", distinct)

with rasterio.open(r"C:\Users\USER\SoilSense ZM\tiff files\phh2o_0-5cm_mean_1000.tif") as src:
    print("Resolution:", src.res)
    print("CRS:", src.crs)
    print("Bounds:", src.bounds)