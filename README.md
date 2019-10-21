# Raspberry Zero GNSS Logger

**Setup**

**1. Dropbox Token**

pi/poweroff.py

*TOKEN = 'put dropbox token here'*

**2. NTRIP**

pi/f9p_navi.conf

*inpstr2-path = put ntrip path here*

*outstr1-path = put tcp client here*

**3. rc.local**

>sudo nano /etc/rc.local

**4. crontab**

>crontab -e