# Probe firmware and bridge: setup guide

The Arduino measures; the laptop bridge talks to it over USB and sends readings to the SoilSense server. Calibration is stored on the server.

> **Not yet checked on real hardware.** The sketch has not been compiled here (the build machine could not download the Arduino board files) and the board gain values in `bridge/boards.py` are typical figures, not confirmed for your boards. Steps 2 and 5 below are where you confirm both.

## What you need

- Arduino Uno and USB cable
- pH sensor board with probe (PH-4502C or DFRobot SEN0161, or similar)
- Capacitive soil moisture sensor v1.2
- DS18B20 waterproof temperature probe and one 4.7 kΩ resistor
- Jumper wires, breadboard
- **pH 7.00 and pH 4.00 buffer** (sachets or bottles) and **distilled water** (see "Buffers" below)

## 1. Wiring

| Part | Part pin | Arduino pin |
|---|---|---|
| pH board | V+ / VCC | 5V |
| pH board | G / GND (both GND pins if there are two) | GND |
| pH board | Po / analogue out | **A0** |
| Moisture sensor | VCC | 5V |
| Moisture sensor | GND | GND |
| Moisture sensor | AOUT | **A1** |
| DS18B20 | red (VCC) | 5V |
| DS18B20 | black (GND) | GND |
| DS18B20 | yellow (data) | **D2**, plus the 4.7 kΩ resistor between D2 and 5V |

PH-4502C boards also have `Do` and `To` pins: leave them unconnected.

## 2. Upload the firmware

1. Install the Arduino IDE (arduino.cc).
2. Tools > Manage Libraries: install **OneWire** (Paul Stoffregen) and **DallasTemperature** (Miles Burton).
3. Open `firmware/soilsense_probe/soilsense_probe.ino`, choose Tools > Board > Arduino Uno and the right port, click Upload.
4. Open Tools > Serial Monitor at 9600 baud with "Newline" line ending. Type `P` and press Enter: you should see `{"ok":true,"fw":"1.0"}`. Type `R`: you should see the pH volts, moisture and temperature.

If it does not compile, copy the error message to Claude.

## 3. Install the bridge

```
pip install -r bridge\requirements.txt
python -m bridge.bridge ports          # find your port, e.g. COM3
python -m bridge.bridge test --port COM3
```

## 4. PH-4502C only: set the zero

Put the probe in the pH 7.00 buffer and run `test` a few times. If the pH volts are far from 2.5 V, turn the potentiometer **next to the BNC socket** slowly until it reads about 2.50 V. Do not touch the other potentiometer (that is for the `Do` pin). This only centres the reading; calibration does the rest.

## 5. Calibrate (start of every session)

Start the server first (`uvicorn backend.main:app`), then:

```
python -m bridge.bridge calibrate --port COM3 --board ph4502c --device probe-1
```

Follow the prompts: rinse, pH 7.00 buffer, wait, Enter; rinse, pH 4.00 buffer, wait, Enter. The server accepts the calibration only if the slope is 95 to 105 %.

**If the slope is far outside (for example 80 % or 120 %) every time, even with fresh buffers**, the board gain is probably wrong. Find the board's volts-per-pH on the seller page or datasheet and work out `gain = (volts per pH) / 0.05916`, then pass it with `--gain`. Tell the developer so the preset in `bridge/boards.py` can be corrected and marked confirmed.

## 6. Take a reading

```
python -m bridge.bridge read --port COM3 --board ph4502c --device probe-1 --field 1
```

The field number is shown in the dashboard address bar (`#/field/1`). Mix air-dried, sieved soil with water at 1:2.5 (for example 20 g soil, 50 ml water; in the field use the scoop and cup), stir, wait, and follow the prompts. Three readings are taken; they must agree within 0.1 pH. The result appears in the dashboard, where you then ask for advice.

## 7. Moisture sensor two-point check (once)

```
python -m bridge.bridge moisture --port COM3
```

Hold the sensor in air, then in water. Send the two numbers to the developer: they set the waterlogging threshold, which is still `OPEN` in the spec.

## Buffers

- **Buy:** pH 7.00 and pH 4.00 buffer. Powder sachets are cheapest and keep longest; each makes a fixed volume (often 250 ml) with distilled water. Ready-made bottles also work. Check the box your pH board came in first: some kits include sachets.
- **Where:** ask the soil lab you send samples to (UNZA Soil Science or ZARI Mount Makulu), a laboratory or scientific supplier in Lusaka, or online.
- **Distilled water:** from a pharmacy. Use it to mix buffers and rinse the probe between buffers and samples.
- **Use:** pour a little buffer into a clean cup for each calibration and throw it away afterwards; never pour used buffer back. Note the buffer temperature (the bridge does this). Made-up powder buffer lasts a few weeks in a closed bottle; check the expiry date.
- **Probe care:** keep the probe tip wet in its storage cap (storage solution or pH 4 buffer), never in distilled water for long, and never let it dry out.
