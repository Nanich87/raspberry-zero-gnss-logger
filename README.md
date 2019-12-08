# Raspberry Zero GNSS Logger

**Setup**

**1. Dropbox Token**

*Installation:*

>pip install dropbox

*Token*

pi/rtk/rtkserver.py

>TOKEN = 'put dropbox token here'

**2. NTRIP**

pi/f9p_navi.conf

>inpstr2-path = put ntrip path here

>outstr1-path = put tcp client here

**3. rc.local**

>sudo nano /etc/rc.local

**4. Compile RTKLIB**

>git clone https://github.com/rtklibexplorer/RTKLIB.git

*Before compiling rtkrcv copy rtkrcv.c from this repository to /home/pi/RTKLIB/app/rtkrcv/*

>sudo apt-get install build-essential

>sudo apt-get install automake

>sudo apt-get install checkinstall

>sudo apt-get install liblapack3

>sudo apt-get install libblas3

>cd RTKLIB/app/rtkrcv/gcc

>sudo make

>sudo make install

**5. Connect GPS**

*See RPi_GPIO.png for pin numbers*

*See ublox-zed-f9p.jpg GPS pins*

>GPS +5V -> PIN04

>GPS GND -> PIN06

>GPS RXD -> PIN08 (GPIO14)

>GPS TXD -> PIN10 (GPIO15)

**6. Connect LED**

>LED- -> PIN09

>LED+ -> PIN11 (GPIO17) - use 500 ohm resistor

**7. Connect Camera Button**

PIN33 & PIN34 (This is for test purposes only. DO NOT connect GPS EXTINT here!!!)

**8. Connect Shutdown Button**

PIN39 & PIN40 (this stops rtkrcv and uploads data to Dropbox, and shuts down Pi)

**9 USB MODEM**

*If you run a modeswitch command on the modem, it will activate itself as a modem instead of mass storage, and your system will automatically detect it as such.*

*Reading your lsusb output, we have this:*

>lsusb

>Bus 002 Device 003: ID 12d1:1f01 Huawei Technologies Co., Ltd. E353/E3131 (Mass storage mode)

*So, let's make the mode auto-set to modem mode. In a terminal, run the following command:*

>sudo nano /lib/udev/rules.d/40-usb_modeswitch.rules

*At the very bottom of the opened file, paste in this exact string:*

#Huawei E353/E3131

ATTR{idVendor}=="12d1", ATTR{idProduct}=="1f01", RUN +="usb_modeswitch '%b/%k'" 

**10. Automatically Mount USB Drives**

>sudo apt install git

>git clone https://github.com/rbrito/usbmount

>sudo apt install debhelper build-essential

>cd usbmount

>dpkg-buildpackage -us -uc -b

>cd ..

>sudo dpkg -i package_name.deb