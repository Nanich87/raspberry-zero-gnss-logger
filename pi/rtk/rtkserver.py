#!/usr/bin/python
from gpiozero import Button
from gpiozero import LED

from RtkController import RtkController

from subprocess import check_output, Popen, PIPE
from threading import Semaphore, Thread

import logging
import json
import time
import os
import signal
import sys
from shutil import copyfile

import reach_tools
import gps_time

from flask import Flask, render_template
from flask_socketio import SocketIO

#RTKLIB_PATH = "/home/pi/RTKLIB"
RTKLIB_PATH = "/home/pi/RTKLIB_2.4.3"
#CONFIG_NAME = "/home/pi/f9p_navi.conf"
CONFIG_NAME = "/home/pi/6m_navi.conf"
LOG_PATH = '/home/pi/log/'

#SERIAL_PORT_BAUD_RATE = 460800
SERIAL_PORT_BAUD_RATE = 115200

CAMERA_PIN_NUMBER = 20
SHUTDOWN_PIN_NUMBER = 21
GREEN_LED_PIN_NUMBER = 19
BLUE_LED_PIN_NUMBER = 6
ORANGE_LED_PIN_NUMBER = 13

NAMESPACE = "/test"

app = Flask(__name__)
app.template_folder = "."
app.config["SECRET_KEY"] = "secret!"
app.rejectUnauthorized = False
socketio = SocketIO(app)

semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = False
time_is_synchronized = False

def initLogging():
	time_mark_log_file = time.strftime("%Y-%m-%d-%H-%M-%S") + '.log';
	time_mark_log_path = os.path.join(LOG_PATH, time_mark_log_file)

	logging.basicConfig(level=logging.INFO,filename=time_mark_log_path,format='%(asctime)s %(message)s')

def sendMessage(message, debug = True):
	socketio.emit("message", message, namespace=NAMESPACE)
	if debug == True:
		print(message)

def backupExternalStorage():
	files = os.listdir(LOG_PATH)
	files.sort()
	for file in files:
		src = os.path.join(LOG_PATH, file)
		dst = os.path.join('/media/usb/', file)

		copyfile(src, dst)
		print(file)


def saveMark():
	semaphore.acquire()

	rtk.getMark()
	print(rtk.mark)
	logging.info(rtk.mark)

	semaphore.release()

def setCorrectTime():
	if not gps_time.time_synchronised_by_ntp():
		sendMessage("Time is not synced by NTP")

		gps_time.set_gps_time("/dev/serial0", SERIAL_PORT_BAUD_RATE)

		global time_is_synchronized
		time_is_synchronized = True

def launchRover(config_name = None):
	semaphore.acquire()

	sendMessage("Attempting to launch rtkrcv...")

	if config_name == None:
		res = rtk.launch()
	else:
		res = rtk.launch(config_name)

	if res < 0:
		sendMessage("rtkrcv launch failed")
	elif res == 1:
		sendMessage("rtkrcv launch successful")
	elif res == 2:
		sendMessage("rtkrcv already launched")

	sendMessage("Rover mode launched")

	semaphore.release()

	return res

def startRover():
	semaphore.acquire()

	sendMessage("Attempting to start rtkrcv...")

	res = rtk.start()

	if res == -1:
		sendMessage("rtkrcv start failed")
	elif res == 1:
		sendMessage("rtkrcv start successful")
	elif res == 2:
		sendMessage("rtkrcv already started")

	global server_not_interrupted
	server_not_interrupted = True

	semaphore.release()

	return res

def stopRover():
	semaphore.acquire()

	sendMessage("Attempting to stop RTKLIB...")

	res = rtk.stop()

	if res == -1:
		sendMessage("rtkrcv stop failed")
	elif res == 1:
		sendMessage("rtkrcv stop successful")
	elif res == 2:
		sendMessage("rtkrcv already stopped")

	global server_not_interrupted
	server_not_interrupted = False

	semaphore.release()

	return res

def shutdownRover():
	semaphore.acquire()

	sendMessage("Attempting rtkrcv shutdown")

	res = rtk.shutdown()

	if res < 0:
		sendMessage("rtkrcv shutdown failed")
	elif res == 1:
		sendMessage("rtkrcv shutdown successful")
	elif res == 2:
		sendMessage("rtkrcv already shutdown")

	sendMessage("Rover mode shutdown")

	semaphore.release()

	return res

def start():
	launchResult = launchRover(CONFIG_NAME)
	if launchResult == 1:
		startResult = startRover()
		if startResult != -1:
			socketio.emit("state", True, namespace=NAMESPACE)
			green_led.on()
		else:
			stopRover()
	else:
		orange_led.on()

def stop():
	stopRover()
	shutdownRover()

	socketio.emit("state", False, namespace=NAMESPACE)

	green_led.off()
	orange_led.off();

def sync():
	blue_led.blink()

	time_thread = Thread(target = setCorrectTime)
	time_thread.start()

	while time_is_synchronized == False:
		time.sleep(5)

	sendMessage("Time is synced")

	blue_led.on()

@app.route("/")
def index():
	return render_template("index.html")

@socketio.on('connect', namespace=NAMESPACE)
def handleConnect():
	socketio.emit("state", server_not_interrupted, namespace=NAMESPACE)
	print("Connected")

@socketio.on('disconnect', namespace=NAMESPACE)
def handleDisconnect():
	print("Disconnected")

@socketio.on('sync', namespace=NAMESPACE)
def handleSync():
        sync()

@socketio.on('start', namespace=NAMESPACE)
def handleStart():
        start()

@socketio.on('stop', namespace=NAMESPACE)
def handleStop():
        stop()

@socketio.on('restart', namespace=NAMESPACE)
def handleRestart():
	stop()
	time.sleep(5)
	start()

@socketio.on('shutdown', namespace=NAMESPACE)
def handleShutdown():
	os.system("sudo shutdown -h now")


if __name__ == "__main__":
	shutdown_button = Button(SHUTDOWN_PIN_NUMBER)
	shutdown_button.when_pressed = handleShutdown

	initLogging()

	green_led = LED(GREEN_LED_PIN_NUMBER)
	blue_led = LED(BLUE_LED_PIN_NUMBER)
	orange_led = LED(ORANGE_LED_PIN_NUMBER)

	try:
		socketio.run(app, host = "0.0.0.0", port = 80, debug=True)
	except KeyboardInterrupt:
		print("Server interrupted by user!")
	finally:
		stop()
