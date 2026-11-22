# Raspberry Zero GNSS Logger

![RTKLIB Control Panel](images/rtklib-control-panel.png "RTKLIB Control Panel")

## Features

* Raw Data Logging
* GPS Time Synchronization
* Start/Stop/Restart Rover
* Device Shutdown (with confirmation)
* File List/Download with size, date and free storage
* Live status: rover, raw logging, GPS time sync, CPU temperature and load
* Mobile-friendly UI with light/dark theme, works fully offline

## Installation

`2021-05-07-raspios-buster-armhf-lite.img`

### Prerequisites

`sudo apt update`

`sudo apt upgrade`

`sudo apt-get install build-essential`

`sudo apt-get install automake`

`sudo apt-get install checkinstall`

`sudo apt-get install liblapack3`

`sudo apt-get install libblas3`

`sudo apt-get install gfortran`

### Python 3

`sudo apt-get install python3-flask python3-flask-socketio python3-pexpect python3-serial python3-gpiozero python3-simple-websocket`

or

`pip3 install -r /home/pi/rtk/requirements.txt`

The web client bundles Socket.IO v4, which requires Flask-SocketIO 5.3 or newer.

### RTKLIB

`cd ~`

`git clone https://github.com/rtklibexplorer/RTKLIB.git`

`cd RTKLIB`

`cd app`

`cd consapp`

`sudo make`

`sudo make install`
