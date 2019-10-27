# Raspberry Zero GNSS Logger

**Setup**

**1. Dropbox Token**

pi/poweroff.py

>TOKEN = 'put dropbox token here'

**2. NTRIP**

pi/f9p_navi.conf

>inpstr2-path = put ntrip path here

>outstr1-path = put tcp client here

**3. rc.local**

>sudo nano /etc/rc.local

**4. Compile RTKLIB**

>sudo apt-get install build-essential

>sudo apt-get install automake

>sudo apt-get install checkinstall

>sudo apt-get install liblapack3

>sudo apt-get install libblas3

>cd RTKLIB

>cd app

>sudo make

>sudo make 

**5. Connect GPS**

*See RPi_GPIO.png for pin numbers*

>GPS VCC -> PIN04

>GPS GND -> PIN06

>GPS RX  -> PIN08 (GPIO14)

>GPS TX  -> PIN10 (GPIO15)

**6. Connect LED**

>LED GND  -> PIN09

>LED VCC  -> PIN11 (GPIO17) - use 500 ohm resistor

**7. Connect Camera Button**

PIN33 & PIN34 (This is for test purposes only. DO NOT connect GPS EXTINT here!!!)

**8. Connect Shutdown Button**

PIN33 & PIN34 (this stops rtkrcv and uploads data to Dropbox, and shuts down Pi)