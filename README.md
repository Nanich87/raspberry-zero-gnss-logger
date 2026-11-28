# Raspberry Zero GNSS Logger

A small, self-contained GNSS logger and RTK rover built on a **Raspberry Pi Zero** and a **u-blox receiver** (NEO-6M or ZED-F9P). It runs [RTKLIB](https://github.com/rtklibexplorer/RTKLIB) and is controlled from a web panel that you open from your phone or laptop in the field. You need no keyboard, no screen and no internet.

![RTKLIB Control Panel](images/rtklib-control-panel.png "RTKLIB Control Panel")

## Contents

- [What it does](#what-it-does)
- [Hardware](#hardware)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Configuration](#configuration)
- [Using the control panel](#using-the-control-panel)
- [Downloading and processing data](#downloading-and-processing-data)
- [Repository layout](#repository-layout)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Credits and license](#credits-and-license)

## What it does

- **Raw data logging.** Records the receiver's raw UBX stream to a file with `str2str`, for post-processing (PPK).
- **RTK rover.** Runs `rtkrcv` with NTRIP corrections and serves the solution as NMEA over TCP.
- **GPS time synchronisation.** The Pi Zero has no real-time clock. When no network time is available, the clock is set from the receiver's UBX `NAV-TIMEUTC` message, so log file names and timestamps are correct.
- **Web control panel** with:
  - start, stop and restart for the rover;
  - start and stop for raw recording;
  - time sync;
  - device shutdown, with a confirmation dialog.
- **Live status:**
  - rover and recording state;
  - time sync state;
  - CPU temperature and load;
  - free storage.
- **File list, download and delete.** Lists the log files with size and date, newest first, and refreshes it automatically. Delete one file or all of them; files still being written are protected.
- **Status LEDs** on GPIO, so you can see the state without opening the panel.
- **OLED status display** (optional SSD1306 on I2C) showing the IP address, the rover's solution, recording and time sync state, the time, CPU temperature and free storage.
- **Rover position and map.** Shows the solution quality (FIX, FLOAT, SINGLE…), satellites, accuracy, age and ratio, and the rover's position and track on a map, coloured by quality.
- **Mobile-friendly panel** with a light and dark theme. All assets are served locally, so it works without internet. Only the map's background tiles need internet on the phone or laptop.

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi Zero / Zero W / Zero 2 W | Any Pi works; the Zero is used for its size and low power |
| u-blox NEO-6M **or** ZED-F9P | Connected to the Pi's UART (`/dev/serial0`) |
| GNSS antenna | Use a multi-band antenna for the ZED-F9P |
| 3 LEDs and resistors (optional) | Status indication |
| SSD1306 OLED, 128×32 or 128×64, I2C (optional) | Status display |
| microSD card, power bank | |

### Wiring

| Receiver | Raspberry Pi |
|---|---|
| TX | GPIO15 / RXD (pin 10) |
| RX | GPIO14 / TXD (pin 8) |
| GND | GND (pin 6) |
| VCC | 3.3 V (pin 1) or 5 V (pin 2), depending on the module |

| LED | GPIO | Physical pin | Meaning |
|---|---|---|---|
| Green | GPIO5 | 29 | Rover is running |
| Blue | GPIO6 | 31 | Blinking: time sync in progress. Steady: time synced |
| Orange | GPIO13 | 33 | Rover failed to start |

| OLED display | Raspberry Pi |
|---|---|
| SDA | GPIO2 / SDA (pin 3) |
| SCL | GPIO3 / SCL (pin 5) |
| VCC | 3.3 V (pin 1) |
| GND | GND (pin 9) |

The display refreshes every second. While the rover runs and has a solution:

```
IP 192.168.1.122
FIX    14sv 0.012m
Rec ON    11:42:07
52C 16.9GB 28.11.26
```

The second line is the solution quality, the number of satellites and the horizontal accuracy (1σ; `H1.2` is HDOP when the profile outputs NMEA). Otherwise it reads `Rover off  Prof m8t`, `Rover RUN  no sol`, or `Rover ERR` when the rover failed to start.

The time and date appear once the clock is set by GPS or NTP. Until then the third line shows `Time --`, or `Time ...` while syncing, and the fourth `52C  Free 16.9GB`.

When you shut the device down from the panel, the display says so.

> The receiver's UART must be set to **115200 baud**. The NEO-6M ships at 9600 and the ZED-F9P at 38400. Change the rate with u-center and save it to the receiver's flash or battery-backed RAM.

## How it works

```
 u-blox receiver ──UART──► /dev/serial0
                               │
          ┌────────────────────┴────────────────────┐
          │                                         │
   str2str (raw logging)                 rtkrcv (RTK rover)
   └► /home/pi/log/<time>.ubx            ├◄ NTRIP corrections (inpstr2)
                                         └► NMEA solution on TCP :27000
          ▲                                         ▲
          └──────────── rtkserver.py ───────────────┘
              Flask + Socket.IO web panel on port 80
              GPIO LEDs · GPS time sync · file downloads
```

- **`rtkserver.py`** is the web server. It starts and stops `str2str` as a subprocess and drives `rtkrcv` through its interactive console, using `pexpect`.
- Raw logging and the rover both use the serial port, so the panel only lets you run one at a time. Time sync also reads the serial port, so it is only available while both are stopped.

## Installation

The paths in the code and config files assume the user is **`pi`** and everything lives in `/home/pi`. Current Raspberry Pi OS images have no default user, so create `pi` in Raspberry Pi Imager when you write the card.

### 1. Operating system

Use **Raspberry Pi OS Lite (32-bit)**. The Trixie release is recommended: it ships every Python dependency as a package. Bookworm also works; see step 3.

Enable the UART and turn off the serial login console:

```sh
sudo raspi-config
# Interface Options → Serial Port
#   Login shell over serial?  → No
#   Serial port hardware?     → Yes
```

On a Pi Zero W or Zero 2 W the main UART is used by Bluetooth. For a more stable serial link, give it back to the GPIO pins by adding this to `/boot/firmware/config.txt`:

```
dtoverlay=disable-bt
```

Then reboot.

### 2. Build tools and directories

```sh
sudo apt update && sudo apt upgrade
sudo apt install git build-essential gfortran
mkdir -p ~/log ~/temp
```

`gfortran` is only needed by RTKLIB's `rnx2rtkp`. `~/log` holds the recordings and `~/temp` is RTKLIB's temporary directory.

### 3. Python dependencies

Trixie:

```sh
sudo apt install python3-flask python3-flask-socketio python3-pexpect \
                 python3-serial python3-gpiozero python3-simple-websocket
```

Bookworm has every package above except `python3-simple-websocket`. Install that one with pip:

```sh
sudo apt install python3-flask python3-flask-socketio python3-pexpect \
                 python3-serial python3-gpiozero python3-pip
sudo pip3 install --break-system-packages simple-websocket
```

`simple-websocket` is optional. Without it the panel still works, but over HTTP long-polling instead of WebSocket.

For the OLED display, enable I2C (`sudo raspi-config` → Interface Options → I2C) and install:

```sh
sudo apt install python3-pil python3-smbus i2c-tools
sudo i2cdetect -y 1    # the display should show up at 3c
```

Without these packages, or without a display, the server runs normally and reports in the **Messages** panel that the display is disabled.

On any other system, use pip with [`pi/rtk/requirements.txt`](pi/rtk/requirements.txt). The panel bundles the Socket.IO v4 client, which needs **Flask-SocketIO 5.3 or newer**.

### 4. RTKLIB

This project uses the [rtklibexplorer](https://github.com/rtklibexplorer/RTKLIB) fork of RTKLIB, pinned to **v2.5.1**. The repository also includes it as the `pi/RTKLIB` submodule.

```sh
cd ~
git clone https://github.com/Nanich87/raspberry-zero-gnss-logger.git
git clone --branch v2.5.1 https://github.com/rtklibexplorer/RTKLIB.git

# Replace rtkrcv.c with the version from this repository (see below)
cp ~/raspberry-zero-gnss-logger/rtkrcv.c ~/RTKLIB/app/consapp/rtkrcv/rtkrcv.c

cd ~/RTKLIB/app/consapp
make
sudo make install
```

The modified `rtkrcv.c` is upstream v2.5.1 with one addition: the `mark` console command also prints the current solution as one line:

```
$MARK,<week>,<tow>,<status>,<lat>,<lon>,<height>,<x>,<y>,<z>
```

`RtkController.getMark()` reads this line.

> Building on a Pi Zero takes a long time, roughly 30 minutes or more. Be patient, or cross-compile.

### 5. Install the logger

```sh
cp -r ~/raspberry-zero-gnss-logger/pi/rtk ~/rtk
cp ~/raspberry-zero-gnss-logger/pi/*.conf ~/raspberry-zero-gnss-logger/pi/*.cmd ~/
```

### 6. Start on boot

The server has to run as root: it uses port 80, GPIO, `date -s` and `shutdown`. Install it as a **systemd service**:

```sh
sudo cp ~/raspberry-zero-gnss-logger/rtkserver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rtkserver
```

The service:

- starts the server at boot and turns off HDMI to save power;
- restarts the server automatically if it crashes;
- sends the server's output to the journal;
- on stop, shuts down `rtkrcv` and `str2str` cleanly.

Useful commands:

```sh
systemctl status rtkserver          # is it running?
journalctl -u rtkserver -f          # follow the server log
sudo systemctl restart rtkserver    # restart after changing files
```

To run it by hand for debugging, stop the service first. Otherwise port 80 is already taken.

```sh
sudo systemctl stop rtkserver
sudo python3 ~/rtk/rtkserver.py
```

<details>
<summary>Alternative: <code>rc.local</code></summary>

The older start-up method still works. Its downside is that the server's output is not saved anywhere and it is not restarted if it crashes. Use it **instead of** the service, not together with it.

```sh
sudo cp ~/raspberry-zero-gnss-logger/rc.local /etc/rc.local
sudo chmod +x /etc/rc.local
```

</details>

Then open **`http://<hostname>.local/`**, for example `http://neo-6m.local/`, or the Pi's IP address.

## Configuration

### Choosing the receiver

Choose the receiver profile in the **Receiver** dropdown in the control panel. You can only change it while the rover is stopped. The choice is saved to `/home/pi/rtk/settings.json` and kept after a reboot.

The dropdown lists every `*_navi.conf` file in `/home/pi`. To add your own profile, copy one of the existing files under a new name, for example `m8t_navi.conf`. To give it a readable name in the dropdown, add it to `PROFILE_NAMES` in `pi/rtk/rtkserver.py`.

Other settings at the top of `pi/rtk/rtkserver.py`:

| Setting | Value |
|---|---|
| `CONFIG_NAME` | `/home/pi/6m_navi.conf`: the profile used until one is chosen in the panel |
| `CONFIG_DIR` | `/home/pi`: where to look for `*_navi.conf` profiles |
| `TIME_SYNC_TIMEOUT` | `900` s: how long to wait for valid GPS time |
| `RTKLIB_PATH` | `/home/pi/RTKLIB` |
| `LOG_PATH` | `/home/pi/log/` |
| `SERIAL_PORT_BAUD_RATE` | `115200` |
| `SOCKET_PORT` | `80` |
| LED pins | GPIO5, GPIO6, GPIO13 |
| `DISPLAY_ENABLED` | `True`: set to `False` if you have no OLED display |
| `DISPLAY_I2C_ADDRESS` | `0x3C`: some displays use `0x3D` |
| `DISPLAY_HEIGHT` | `32`: set to `64` for a 128×64 display |

### Receiver profiles

| | `6m_navi.conf` (NEO-6M) | `m8t_navi.conf` (NEO-M8T) | `f9p_navi.conf` (ZED-F9P) |
|---|---|---|---|
| Frequencies | L1 | L1 | L1 + L2 |
| Constellations | GPS + SBAS | GPS + GLONASS + Galileo | GPS + GLONASS + Galileo |
| Ambiguity resolution | fix-and-hold | fix-and-hold, GLONASS AR fix-and-hold | fix-and-hold, GLONASS AR on |
| Solution output | NMEA :27000 | NMEA :27000, llh :27100 | NMEA :27000 |
| Startup commands | `6m.cmd` | `m8t.cmd` | `f9p.cmd` |

All profiles use kinematic mode with a 15° elevation mask.

The startup command file is sent to the receiver when `rtkrcv` starts:

- **`6m.cmd`** turns on raw measurement output on the NEO-6M (`RXM-RAW`, `RXM-SFRB`). It uses an undocumented command that works on firmware 7.03.
- **`m8t.cmd`** sets 1 Hz and turns on everything `rtkrcv` needs on UART1: raw measurements (`RXM-RAWX`), navigation subframes (`RXM-SFRBX`) and time marks (`TIM-TM2`). It turns NMEA off on UART1 only, so u-center still works over USB. So the rover works even after the receiver loses its saved settings.
- **`f9p.cmd`** turns on `TIM-TM2` time-mark messages, for event logging through the EXTINT pin.

For a stable fix, the antenna needs open sky: satellites above 30° should show 40 dB or more. With the M8T on a roof antenna and VRS corrections, the rover holds a fix every epoch, with about 1 cm scatter. Indoors or by a window, high satellites drop to 25–33 dB and it stays FLOAT whatever the settings.

### NTRIP corrections

Set your caster in the `.conf` file:

```
inpstr2-type   =ntripcli
inpstr2-path   =username:password@host:port/mountpoint
inpstr2-nmeareq=single      # send the rover's position to the caster (needed for VRS / nearest-base)
```

For a VRS or nearest-base mountpoint, also check these two settings. All three profiles have them:

```
out-outsingle  =on          # keep single solutions; without it, the caster gets an empty position
ant2-postype   =rtcm        # take the base position from the RTCM stream
```

With `out-outsingle=off`, RTKLIB marks a single solution as "no solution" in RTK modes. It then sends the caster an empty `$GPGGA,,,,` sentence, the caster sends no corrections, and without corrections there is never a solution: the rover stays without a position. The caster's reply is logged to `base_*.rtcm3` when `logstr2` is on; if that file stays at a few dozen bytes, this is the likely cause.

The first connection may time out because the rover has no position yet; `rtkrcv` reconnects after `misc-reconnect` (10 s) and the corrections then arrive.

`inpstr2-nmealat` / `inpstr2-nmealon` are only used with `inpstr2-nmeareq=latlon`, which always sends that fixed position.

### Solution output

The rover publishes its solution as **NMEA on TCP port 27000** (`outstr2`). Connect any NMEA-over-TCP client to `<pi-address>:27000`, for example QGIS or a mapping app on your phone.

The control panel and the display read the solution from the profile's own TCP server output. They use the first `outstr1`/`outstr2` with type `tcpsvr` and format `llh`, or `nmea` if there's no `llh` one. With `llh` you also get accuracy (standard deviations), age and ratio; with `nmea`, HDOP instead. A profile without such an output still works, but shows no position. The panel says so in **Messages**.

In `kinematic` and other RTK modes, `rtkrcv` outputs a solution only while corrections arrive from the base. If the map keeps saying "No solution yet", check the NTRIP stream (the `base_*.rtcm3` log should grow).

You can also record the rover's input streams by setting `logstr1-type` and `logstr2-type` to `file`. The paths are already set to `/home/pi/log/rover_*.ubx` and `base_*.rtcm3`.

## Using the control panel

| Control | Action | Available when |
|---|---|---|
| **Receiver** dropdown | Chooses the `rtkrcv` profile (NEO-6M, ZED-F9P, …) | Rover stopped |
| **Start rover** | Launches `rtkrcv` with the selected profile and starts the solution | Rover and recording stopped |
| **Stop rover** | Stops and shuts down `rtkrcv` | Rover running |
| **Restart** | Stop, wait 5 s, start | Rover running |
| **Record raw** / **Stop recording** | Starts or stops `str2str`, writing `/home/pi/log/YYYY-MM-DD-HH-MM-SS.ubx` | Rover stopped |
| **Sync time** | Sets the system clock from GPS, if NTP has not already synced it | Rover and recording stopped |
| **Shut down** | Powers off the Pi, after a confirmation | Recording stopped |

Typical field workflow:

1. Power on and wait about 30 s.
2. Open the panel and press **Sync time**.
3. Press **Record raw** or **Start rover**.
4. Stop it, download the files and press **Shut down** before you cut the power.

The **Position** panel shows the current solution and a map of the rover's track: one point per second, kept for the last hour, green for FIX, orange for FLOAT, blue for DGPS and red for SINGLE. The map follows the rover until you pan it; the target button turns following back on, and the trash button clears the track. The background map comes from OpenStreetMap through the device you view the panel on; without internet the track is drawn on a grid with a scale bar.

The **Messages** panel shows what the server is doing, with timestamps. The **Logs** panel lists every file in `/home/pi/log`, newest first. Each server start also creates a `<time>.log` file there, containing the web server's request log.

To free space, click the trash icon next to a file, or the trash icon in the **Logs** header to delete all files. Both ask for confirmation. Files that a process has open can't be deleted and are marked **REC** or **IN USE**: the running recording, the rover's logs while it runs, and the server's current `.log` file.

## Downloading and processing data

Click the download icon next to a file in the **Logs** panel, or copy the files over SSH:

```sh
scp pi@neo-6m.local:log/*.ubx .
```

To convert raw UBX to RINEX for post-processing with RTKLIB:

```sh
convbin -r ubx -od -os 2026-11-22-10-00-00.ubx
```

Process the RINEX files with `rnx2rtkp` or RTKPOST, using base station or CORS data.

## Repository layout

```
├── pi/
│   ├── rtk/                    Web server and control panel → /home/pi/rtk
│   │   ├── rtkserver.py        Flask + Socket.IO server, GPIO, str2str/rtkrcv control
│   │   ├── RtkController.py    Drives the rtkrcv console through pexpect
│   │   ├── gps_time.py         Sets the system clock from UBX NAV-TIMEUTC
│   │   ├── display.py          SSD1306 OLED status display over I2C
│   │   ├── solution.py         Reads rtkrcv's llh / NMEA solution output
│   │   ├── reach_tools.py      Helpers
│   │   ├── index.html          Control panel page
│   │   ├── static/             CSS, JS, bundled Socket.IO client and Leaflet
│   │   ├── requirements.txt    Python dependencies
│   │   └── settings.json       Selected receiver profile (created at runtime)
│   ├── 6m_navi.conf, 6m.cmd    NEO-6M rtkrcv profile and receiver commands
│   ├── m8t_navi.conf, m8t.cmd  NEO-M8T rtkrcv profile and receiver commands
│   ├── f9p_navi.conf, f9p.cmd  ZED-F9P rtkrcv profile and receiver commands
│   └── RTKLIB/                 RTKLIB submodule (v2.5.1)
├── rtkrcv.c                    rtkrcv with the extended "mark" command
├── rtkserver.service           systemd service → /etc/systemd/system
├── rc.local                    Alternative boot script → /etc/rc.local
└── images/                     Screenshot
```

## Troubleshooting

**The panel doesn't open.**

- Check that the server is running: `systemctl status rtkserver`.
- Look for errors in its log: `journalctl -u rtkserver -n 50`.
- If you see `ModuleNotFoundError`, install the missing package from step 3.

**"rtkrcv launch failed" and the orange LED is on.**

- Check that `/home/pi/RTKLIB/app/consapp/rtkrcv/gcc/rtkrcv` exists, i.e. that RTKLIB was built.
- Check that the profile chosen in the **Receiver** dropdown is the right one for your receiver.
- Check that nothing else is holding the serial port (raw recording, or a serial console).

**No data, or garbage data, from the receiver.**

- Check the baud rate: it must be 115200 on both sides.
- Check that TX and RX are crossed.
- Check that the serial login console is disabled.
- Test the port directly: `sudo cat /dev/serial0 | xxd | head`.

**"Time sync failed: no valid GPS time".** The receiver did not report a valid UTC time within 15 minutes (`TIME_SYNC_TIMEOUT`). After a cold start it needs a fix and the leap-second count from the almanac, which can take up to 12.5 minutes. Move the antenna to a place with a clear view of the sky and press **Sync time** again.

**"display not found on I2C bus 1" or a blank display.**

- Check that I2C is enabled and the wiring is right: `sudo i2cdetect -y 1` should show `3c` (or `3d`).
- If the address is `3d`, set `DISPLAY_I2C_ADDRESS = 0x3D`.
- The server looks for the display again every 30 seconds, so you can connect it while it runs.

**"Str2Str stopped unexpectedly".** The recording process exited on its own. The text in brackets is its last error, usually the serial port being busy or missing.

**Log files have dates in 1970 or in the past.** The clock was not synced before recording started. Press **Sync time** first, or give the Pi a network connection so NTP can set it.

## Security

The control panel has **no authentication**. Anyone who can reach port 80 can start and stop logging, download files and shut down the device. Use it only on a network you trust, such as the Pi's own hotspot or your phone's tethering.

## Credits and license

- **RTKLIB** by T. Takasu, rtklibexplorer fork. BSD 2-clause license.
- `RtkController.py`, `gps_time.py` and `reach_tools.py` are based on **ReachView** by Emlid Ltd. and are licensed under the **GNU GPL v3**.
- The bundled **Socket.IO** client is MIT-licensed.
- The bundled **Leaflet** 1.9.4 is BSD 2-clause licensed (`pi/rtk/static/leaflet/LICENSE`).
- Map data © **OpenStreetMap** contributors. The tiles come from the OpenStreetMap tile servers, whose [usage policy](https://operations.osmfoundation.org/policies/tiles/) allows light personal use like this.
