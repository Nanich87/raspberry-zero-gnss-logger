#!/usr/bin/python
from gpiozero import LED, CPUTemperature, LoadAverage
from RtkController import RtkController
from subprocess import check_output, Popen, PIPE
from threading import Semaphore, Thread

import subprocess
import logging
import json
import time
import os
import signal
import sys

import reach_tools
import gps_time

from flask import Flask, render_template, send_file
from flask_socketio import SocketIO

# RTKLIB
RTKLIB_PATH = "/home/pi/RTKLIB"
CONFIG_NAME = "/home/pi/6m_navi.conf"
LOG_PATH = "/home/pi/log/"
STR2STR_PATH = "app/consapp/str2str/gcc/str2str"

# Serial
SERIAL_PORT_BAUD_RATE = 115200

# LEDs
BLUE_LED_PIN_NUMBER = 6
GREEN_LED_PIN_NUMBER = 5
ORANGE_LED_PIN_NUMBER = 13

# SocketIO
SOCKET_HOST = "0.0.0.0"
SOCKET_PORT = 80
SOCKET_NAMESPACE = "/test"

# App
app = Flask(__name__)
app.template_folder = "."
app.config["SECRET_KEY"] = "secret!"
app.rejectUnauthorized = False
app.debug = True

socketio = SocketIO(app)

# RtkController
semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = False
time_is_synchronized = False
wifi_is_enabled = True
proc = None

# CPU
cpu = CPUTemperature()
la = LoadAverage(min_load_average=0, max_load_average=2)

def initLogging():
	time_mark_log_file = time.strftime("%Y-%m-%d-%H-%M-%S") + '.log';
	time_mark_log_path = os.path.join(LOG_PATH, time_mark_log_file)

	logging.basicConfig(level=logging.INFO,filename=time_mark_log_path,format='%(asctime)s %(message)s')

def sendMessage(message, debug = True):
	socketio.emit("message", message, namespace=SOCKET_NAMESPACE)
	if debug == True:
		print(message)

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

	if res == -1:
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
			socketio.emit("state", True, namespace=SOCKET_NAMESPACE)
			green_led.on()
		else:
			stopRover()
	else:
		orange_led.on()

def stop():
	stopRover()
	shutdownRover()

	socketio.emit("state", False, namespace=SOCKET_NAMESPACE)

	green_led.off()
	orange_led.off()

def str2str():
	global proc
	if proc is None:
		args = os.path.join(RTKLIB_PATH, STR2STR_PATH) + ' -in serial://serial0:' + '{0}'.format(SERIAL_PORT_BAUD_RATE) + ':8:n:1:off -out '+ os.path.join(LOG_PATH, time.strftime("%Y-%m-%d-%H-%M-%S")) + '.ubx'
		proc = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE, preexec_fn=os.setsid)
		socketio.emit("str2str", True, namespace=SOCKET_NAMESPACE)
		sendMessage("Str2Str started")
		sendMessage(args)
	else:
		os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
		proc = None
		socketio.emit("str2str", False, namespace=SOCKET_NAMESPACE)
		sendMessage("Str2Str stopped")

def sync():
	if time_is_synchronized == True:
		sendMessage("Time is synced")
		return

	blue_led.blink()

	time_thread = Thread(target = setCorrectTime)
	time_thread.start()

	while time_is_synchronized == False:
		time.sleep(5)

	sendMessage("Time is synced")

	blue_led.on()

def turnOffLeds():
        blue_led.off()
        green_led.off()
        orange_led.off();

@app.route("/")
def index():
	#files = os.listdir(LOG_PATH)
	files = filter(lambda x: os.path.isfile(os.path.join(LOG_PATH, x)), os.listdir(LOG_PATH))
	files = sorted(files, key = lambda x: os.path.getmtime(os.path.join(LOG_PATH, x)))
	return render_template("index.html", files=files)

@app.route("/download/<file>")
def getPath(file):
	return send_file(os.path.join(LOG_PATH, file), as_attachment=True)

@socketio.on('connect', namespace=SOCKET_NAMESPACE)
def handleConnect():
	socketio.emit("state", server_not_interrupted, namespace=SOCKET_NAMESPACE)

@socketio.on('disconnect', namespace=SOCKET_NAMESPACE)
def handleDisconnect():
	print("Disconnected")

@socketio.on('str2str', namespace=SOCKET_NAMESPACE)
def handleSync():
        str2str()

@socketio.on('sync', namespace=SOCKET_NAMESPACE)
def handleSync():
        sync()

@socketio.on('start', namespace=SOCKET_NAMESPACE)
def handleStart():
        start()

@socketio.on('stop', namespace=SOCKET_NAMESPACE)
def handleStop():
        stop()

@socketio.on('restart', namespace=SOCKET_NAMESPACE)
def handleRestart():
	stop()
	time.sleep(5)
	start()

@socketio.on('shutdown', namespace=SOCKET_NAMESPACE)
def handleShutdown():
	turnOffLeds()
	os.system("sudo shutdown -h now")

@socketio.on('cpu', namespace=SOCKET_NAMESPACE)
def handleCpu():
	socketio.emit("cpu", cpu.temperature, namespace=SOCKET_NAMESPACE)

@socketio.on('load', namespace=SOCKET_NAMESPACE)
def handleCpu():
        socketio.emit("load", la.load_average*100, namespace=SOCKET_NAMESPACE)

def handleWifi():
	global wifi_is_enabled
	if wifi_is_enabled:
		subprocess.call(['sudo', 'iwconfig', 'wlan0', 'txpower', 'off'])
		wifi_is_enabled = False
	else:
		subprocess.call(['sudo', 'iwconfig', 'wlan0', 'txpower', 'auto'])
		wifi_is_enabled = True

if __name__ == "__main__":
	initLogging()

	green_led = LED(GREEN_LED_PIN_NUMBER)
	blue_led = LED(BLUE_LED_PIN_NUMBER)
	orange_led = LED(ORANGE_LED_PIN_NUMBER)

	try:
		socketio.run(app, host = SOCKET_HOST, port = SOCKET_PORT)
	except KeyboardInterrupt:
		print("Server interrupted by user!")
	finally:
		stop()
