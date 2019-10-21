import RPi.GPIO as GPIO
from gpiozero import Button

from RtkController import RtkController

from subprocess import check_output, Popen, PIPE
from threading import Semaphore, Thread

import logging
import json
import time
import os
import signal

RTKLIB_PATH = "/home/pi/RTKLIB"
CONFIG_NAME = "/home/pi/f9p_navi.conf"
CAMERA_LOG_PATH = "/home/pi/rtk/rtk.log"
CAMERA_PIN_NUMBER = 13

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(CAMERA_PIN_NUMBER, GPIO.IN, pull_up_down=GPIO.PUD_UP)

logging.basicConfig(level=logging.INFO,filename=CAMERA_LOG_PATH,format='%(asctime)s %(message)s')

semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = True

def saveMark():
	semaphore.acquire()

	rtk.getMark()
	print(rtk.mark)
	logging.info(rtk.mark)

	semaphore.release()

def launchRover(config_name = None):
	semaphore.acquire()
        print("Attempting to launch rtkrcv...")

        if config_name == None:
        	res = rtk.launch()
        else:
        	res = rtk.launch(config_name)

        if res < 0:
        	print("rtkrcv launch failed")
        elif res == 1:
            	print("rtkrcv launch successful")
        elif res == 2:
            	print("rtkrcv already launched")

        print("Rover mode launched")

        semaphore.release()

        return res

def startRover():
        semaphore.acquire()
        print("Attempting to start rtkrcv...")

        res = rtk.start()

        if res == -1:
            	print("rtkrcv start failed")
        elif res == 1:
            	print("rtkrcv start successful")
            	print("Starting coordinate and satellite broadcast")
        elif res == 2:
            	print("rtkrcv already started")

	global server_not_interrupted
	server_not_interrupted = True

        semaphore.release()

        return res

def stopRover():
        semaphore.acquire()
        print("Attempting to stop RTKLIB...")

        res = rtk.stop()

        if res == -1:
            	print("rtkrcv stop failed")
        elif res == 1:
            	print("rtkrcv stop successful")
        elif res == 2:
            	print("rtkrcv already stopped")

	global server_not_interrupted
        server_not_interrupted = False

        semaphore.release()

        return res

def shutdownRover():
        semaphore.acquire()
        print("Attempting rtkrcv shutdown")

        res = rtk.shutdown()

        if res < 0:
        	print("rtkrcv shutdown failed")
        elif res == 1:
            	print("rtkrcv shutdown successful")
        elif res == 2:
            	print("rtkrcv already shutdown")

        print("Rover mode shutdown")

        semaphore.release()

        return res

if __name__ == "__main__":
	try:
		camera_button = Button(CAMERA_PIN_NUMBER)
		camera_button.when_pressed = saveMark

        	res = launchRover(CONFIG_NAME)

 		if res == 1:
            		startRover()
		while True:
			time.sleep(5)

    	except KeyboardInterrupt:
        	print("Server interrupted by user!")

	finally:
		stopRover()
		shutdownRover()
