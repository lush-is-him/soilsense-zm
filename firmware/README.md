# Probe firmware and bridge: setup guide

The Arduino measures; the laptop bridge talks to it over USB and sends readings to the SoilSense server. Calibration is stored on the server.

> **Not yet checked on real hardware.** Parts confirmed from photos: PH-4502C, capacitive moisture v2.0, KY-001. The sketch has not been compiled here (the build machine could not download the Arduino board files) and the board gain values in `bridge/boards.py` are typical figures, not confirmed for your boards. Steps 2 and 5 below are where you confirm both.

## Your parts (identified from photos, 29 Oct 2026)

| Part | What it is | Notes |
|---|---|---|
| Green board with BNC socket, pins `To Do Po G G V+`, two blue potentiometers | **PH-4502C** pH board | Use `--board ph4502c` with the bridge |
| pH probe (white and blue top, glass bulb in a storage bottle) | Combination pH electrode (BNC) | Keep the bulb wet in its storage bottle |
| Black board "Capacitive Soil Moisture Sensor v2.0", 3-wire plug | Capacitive moisture sensor | Wires: usually black GND, red VCC, yellow AOUT; check the labels next to the plug |
| Small black board, 3 pins marked `S`, middle, `-`, with a 3-leg chip and a small LED | **KY-001** temperature module (DS18B20 chip, pull-up resistor already on the board) | **Not waterproof.** See "Temperature" below |
| Arduino Uno and USB cable | | |

You also need: **pH 4.00 and 7.00 buffer** and **distilled water** (see "Buffers"), jumper wires, and a breadboard if you have one (two GND and two 5V wires need to share the Uno's pins).

## 1. Wiring

Unplug the Uno from USB while wiring.

| From | Pin on the part | To Arduino pin |
|---|---|---|
| PH-4502C | **V+** | **5V** |
| PH-4502C | **G** (either of the two) | **GND** |
| PH-4502C | **Po** | **A0** |
| PH-4502C | To, Do, the other G | nothing |
| Moisture sensor | VCC (red) | **5V** |
| Moisture sensor | GND (black) | **GND** |
| Moisture sensor | AOUT (yellow) | **A1** |
| KY-001 | **middle pin** | **5V** |
| KY-001 | **-** | **GND** |
| KY-001 | **S** | **D2** |

The Uno has one 5V pin and three GND pins. For three parts on 5V, put the 5V wire on the breadboard's red (+) rail and plug all three VCC/V+ wires into that rail. Without a breadboard you can twist the three 5V wire ends together with the one from the Uno and tape them, but a breadboard is much more reliable.

The KY-001 already has its 4.7 kΩ resistor on the board: do not add another.

### Temperature

The KY-001 cannot go into the soil-water mix: it is a bare chip on a circuit board. Two options:

1. **Best:** buy a *waterproof DS18B20 probe* (a steel tube on a cable, three wires; very cheap where Arduino parts are sold). It plugs into the same pins (red 5V, black GND, yellow D2) and needs a 4.7 kΩ resistor between yellow and 5V, or keep the KY-001 board and connect the probe's wires to its pins instead of the chip. No code change.
2. **For now:** keep the KY-001 next to the cup. Indoors, when the buffers and the soil mix have stood in the same room for 30 minutes, they are close to room temperature, so the reading is a fair stand-in. Say so in the dissertation (method limitation).

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

## Port problems (Windows, CH340 clone boards)

Symptom: uploads or `python -m bridge.bridge test` work after a restart, then fail with "cannot set com-state", "unable to open port" or "A device attached to the system is not functioning".

1. **Only one program at a time.** Close the Arduino IDE completely (check Task Manager for "Arduino IDE") before running the bridge. The firmware stays on the Arduino; the IDE is only needed to upload it again.
2. **Unplug and replug** the USB cable instead of restarting the laptop.
3. **Find out whether the sensors cause it.** Pull the two 5V wires (pH board V+, temperature middle) out of the Arduino, replug the USB, and run `test` several times over a few minutes. If it now stays working, a sensor wire is shorting or loose: recheck the wiring against the table.
4. **Driver.** Device Manager → Ports → USB-SERIAL CH340 → Properties → Driver: if **Roll Back Driver** is available, use it. Otherwise Update driver → Browse my computer → Let me pick → choose an older CH340 version if more than one is listed. Recent CH340 drivers are known to misbehave with the copied CH340 chips on clone boards.
5. **USB power saving.** Device Manager → Universal Serial Bus controllers → each USB Root Hub → Properties → Power Management → untick "Allow the computer to turn off this device to save power".
