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

**4. crontab**

>crontab -e

**5. Compile RTKLIB**

>sudo apt-get install build-essential

>sudo apt-get install automake

>sudo apt-get install checkinstall

>sudo apt-get install liblapack3

>sudo apt-get install libblas3

>cd RTKLIB

>cd app

>sudo make

>sudo make install