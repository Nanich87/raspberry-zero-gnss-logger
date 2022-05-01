# Raspberry Zero GNSS Logger

![RTKLIB Control Panel](https://github.com/Nanich87/raspberry-zero-gnss-logger/blob/master/images/rtklib-control-panel.png "RTKLIB Control Panel")

## Features

* Raw Data Logging
* GPS Time Synchronization
* Start/Stop/Restart Rover
* Device Shutdown
* File List/Download

## RTKLIB

`sudo apt-get install build-essential

`sudo apt-get install automake

`sudo apt-get install checkinstall

`sudo apt-get install liblapack3

`sudo apt-get install libblas3

`sudo apt-get install gfortran

`cd ~

`git clone https://github.com/rtklibexplorer/RTKLIB.git

`cd RTKLIB

`cd app

`cd consapp

`sudo make

`sudo make install
