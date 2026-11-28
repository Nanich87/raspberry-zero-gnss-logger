#!/usr/bin/env python3
from gpiozero import LED, CPUTemperature, LoadAverage
from RtkController import RtkController
from subprocess import check_output, Popen, PIPE
from threading import Lock, Semaphore, Thread

import subprocess
import logging
import glob
import json
import time
import os
import shutil
import signal
import sys

import reach_tools
import gps_time
from display import StatusDisplay

from flask import Flask, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO, emit

# RTKLIB
RTKLIB_PATH = "/home/pi/RTKLIB"
CONFIG_NAME = "/home/pi/6m_navi.conf"   # default receiver profile

# Receiver profiles: every *_navi.conf in CONFIG_DIR can be selected in the panel
CONFIG_DIR = "/home/pi"
PROFILE_PATTERN = "*_navi.conf"
PROFILE_NAMES = {
	"6m_navi.conf": "u-blox NEO-6M",
	"m8t_navi.conf": "u-blox NEO-M8T",
	"f9p_navi.conf": "u-blox ZED-F9P",
}
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
LOG_PATH = "/home/pi/log/"
STR2STR_PATH = "app/consapp/str2str/gcc/str2str"

# Serial
SERIAL_PORT_BAUD_RATE = 115200

# GPS time sync: give up if no valid UTC time arrives within this many seconds.
# After a cold start the receiver may need up to 12.5 min to get the leap
# second count from the almanac before it reports valid UTC.
TIME_SYNC_TIMEOUT = 15 * 60

# LEDs
BLUE_LED_PIN_NUMBER = 6
GREEN_LED_PIN_NUMBER = 5
ORANGE_LED_PIN_NUMBER = 13

# OLED status display (SSD1306 on I2C). Set DISPLAY_ENABLED = False if you have none.
DISPLAY_ENABLED = True
DISPLAY_I2C_BUS = 1
DISPLAY_I2C_ADDRESS = 0x3C
DISPLAY_HEIGHT = 32        # 32 or 64
DISPLAY_REFRESH = 2        # seconds between updates
DISPLAY_RETRY = 30         # seconds between attempts to find a missing display

# SocketIO
SOCKET_HOST = "0.0.0.0"
SOCKET_PORT = 80
SOCKET_NAMESPACE = "/test"

# App
app = Flask(__name__)
app.template_folder = "."
app.config["SECRET_KEY"] = "secret!"
app.rejectUnauthorized = False
app.debug = False

socketio = SocketIO(app)

@app.url_defaults
def versionStatic(endpoint, values):
	"""Add ?v=<mtime> to static URLs, so browsers fetch a file again after it
	changes instead of using a cached copy (older versions sent max-age=12h)."""
	if endpoint == "static" and "filename" in values:
		try:
			values["v"] = int(os.stat(os.path.join(app.static_folder, values["filename"])).st_mtime)
		except OSError:
			pass

# RtkController
semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = False
time_is_synchronized = False
time_sync_in_progress = False
wifi_is_enabled = True
proc = None
proc_lock = Lock()
current_profile = os.path.basename(CONFIG_NAME)

# CPU
cpu = CPUTemperature()
la = LoadAverage(min_load_average=0, max_load_average=2)

# Display
display = StatusDisplay(DISPLAY_I2C_BUS, DISPLAY_I2C_ADDRESS, height=DISPLAY_HEIGHT)
display_stopped = False

def listProfiles():
	files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(CONFIG_DIR, PROFILE_PATTERN)))
	return [{"file": f, "name": PROFILE_NAMES.get(f, f)} for f in files]

def loadProfile():
	"""Return the saved profile if it still exists, otherwise the default."""
	try:
		with open(SETTINGS_FILE) as f:
			saved = json.load(f).get("profile")
		if saved in [p["file"] for p in listProfiles()]:
			return saved
	except (OSError, ValueError):
		pass
	return os.path.basename(CONFIG_NAME)

def saveProfile(name):
	tmp = SETTINGS_FILE + ".tmp"
	with open(tmp, "w") as f:
		json.dump({"profile": name}, f)
	os.replace(tmp, SETTINGS_FILE)

def profilesPayload():
	return {"profiles": listProfiles(), "selected": current_profile}

def initLogging():
	time_mark_log_file = time.strftime("%Y-%m-%d-%H-%M-%S") + '.log';
	time_mark_log_path = os.path.join(LOG_PATH, time_mark_log_file)

	logging.basicConfig(level=logging.INFO,filename=time_mark_log_path,format='%(asctime)s %(message)s')

def sendMessage(message, debug = True):
	socketio.emit("message", message, namespace=SOCKET_NAMESPACE)
	if debug == True:
		print(message)

def setCorrectTime():
	"""Sync the clock (NTP or GPS). Runs in a background task started by sync()."""
	global time_is_synchronized, time_sync_in_progress

	synced = False
	try:
		if gps_time.time_synchronised_by_ntp():
			sendMessage("Time synced by NTP")
			synced = True
		else:
			sendMessage("No NTP time, waiting for valid GPS time (up to %d min)..." % (TIME_SYNC_TIMEOUT // 60))
			result = gps_time.set_gps_time("/dev/serial0", SERIAL_PORT_BAUD_RATE, timeout=TIME_SYNC_TIMEOUT)
			if result == "gps":
				sendMessage("Time synced from GPS (UTC)")
				synced = True
			elif result == "ntp":
				sendMessage("Time synced by NTP")
				synced = True
			else:
				sendMessage("Time sync failed: no valid GPS time within %d min. Check the antenna and try again." % (TIME_SYNC_TIMEOUT // 60))
	except Exception as e:
		sendMessage("Time sync failed: %s" % e)
	finally:
		time_sync_in_progress = False

	if synced:
		time_is_synchronized = True
		blue_led.on()
	else:
		blue_led.off()

	socketio.emit("timesync", synced, namespace=SOCKET_NAMESPACE)

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
	sendMessage("Receiver profile: %s" % PROFILE_NAMES.get(current_profile, current_profile))
	launchResult = launchRover(os.path.join(CONFIG_DIR, current_profile))
	if launchResult == 1:
		startResult = startRover()
		if startResult != -1:
			socketio.emit("state", True, namespace=SOCKET_NAMESPACE)
			green_led.on()
		else:
			stopRover()
			socketio.emit("state", False, namespace=SOCKET_NAMESPACE)
	else:
		orange_led.on()
		socketio.emit("state", False, namespace=SOCKET_NAMESPACE)

def stop():
	stopRover()
	shutdownRover()

	socketio.emit("state", False, namespace=SOCKET_NAMESPACE)

	green_led.off()
	orange_led.off()

def watchStr2str(p):
	"""Read str2str's output until it exits; report it if it exits on its own."""
	global proc

	last_line = ""
	for raw in p.stderr:
		line = raw.decode("utf-8", errors="replace").strip()
		if line:
			last_line = line
	code = p.wait()

	with proc_lock:
		if proc is not p:
			return  # stopped from the panel
		proc = None

	reason = " (%s)" % last_line if last_line else ""
	sendMessage("Str2Str stopped unexpectedly, exit code %d%s" % (code, reason))
	socketio.emit("str2str", False, namespace=SOCKET_NAMESPACE)

def str2str():
	global proc
	with proc_lock:
		if proc is None:
			args = os.path.join(RTKLIB_PATH, STR2STR_PATH) + ' -in serial://serial0:' + '{0}'.format(SERIAL_PORT_BAUD_RATE) + ':8:n:1:off -out '+ os.path.join(LOG_PATH, time.strftime("%Y-%m-%d-%H-%M-%S")) + '.ubx'
			proc = subprocess.Popen(args, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=os.setsid)
			socketio.start_background_task(watchStr2str, proc)
			socketio.emit("str2str", True, namespace=SOCKET_NAMESPACE)
			sendMessage("Str2Str started")
			sendMessage(args)
		else:
			try:
				os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
			except ProcessLookupError:
				pass  # already exited
			proc = None
			socketio.emit("str2str", False, namespace=SOCKET_NAMESPACE)
			sendMessage("Str2Str stopped")

def sync():
	if time_is_synchronized == True:
		sendMessage("Time is synced")
		socketio.emit("timesync", True, namespace=SOCKET_NAMESPACE)
		return

	global time_sync_in_progress
	if time_sync_in_progress:
		return
	time_sync_in_progress = True

	blue_led.blink()
	socketio.emit("timesync", "pending", namespace=SOCKET_NAMESPACE)

	# don't block the Socket.IO handler; setCorrectTime reports the result
	socketio.start_background_task(setCorrectTime)

def getIp():
	try:
		ips = check_output(["hostname", "-I"], timeout=5).decode().split()
	except (OSError, subprocess.SubprocessError):
		ips = []
	return ips[0] if ips else "no network"

def displayLines():
	if server_not_interrupted:
		rover = "RUN"
	elif orange_led.is_lit:
		rover = "ERR"
	else:
		rover = "off"

	if time_sync_in_progress:
		synced = "..."
	elif time_is_synchronized:
		synced = "OK"
	else:
		synced = "--"

	profile = current_profile.replace("_navi.conf", "")
	free_gb = shutil.disk_usage(LOG_PATH).free / 1e9

	return [
		"IP " + getIp(),
		"Rover %-4s Prof %s" % (rover, profile),
		"Rec %-4s  Time %s" % ("ON" if proc is not None else "off", synced),
		"%.0fC  Free %.1fGB" % (cpu.temperature, free_gb),
	]

def displayLoop():
	"""Refresh the OLED in the background; retry now and then if it is missing."""
	reported = ""   # differs from any real state, so the first one is reported
	next_try = 0
	while not display_stopped:
		if not display.available and time.time() >= next_try:
			display.begin()
			next_try = time.time() + DISPLAY_RETRY
		if display.available:
			try:
				lines = displayLines()
			except Exception as e:
				lines = ["Display error", str(e)]
			with display.lock:   # don't overwrite the shutdown message
				if not display_stopped:
					display.show(lines)

		if display.error != reported:
			reported = display.error
			if reported:
				sendMessage(reported)
			elif display.available:
				sendMessage("Status display connected")

		socketio.sleep(DISPLAY_REFRESH)

def stopDisplay(lines = None):
	global display_stopped
	with display.lock:
		display_stopped = True
		if lines:
			display.show(lines)
		else:
			display.off()

def turnOffLeds():
        blue_led.off()
        green_led.off()
        orange_led.off();

@app.route("/")
def index():
	return render_template("index.html", hostname=os.uname().nodename)

@app.route("/api/files")
def listFiles():
	files = []
	for name in os.listdir(LOG_PATH):
		path = os.path.join(LOG_PATH, name)
		if os.path.isfile(path):
			st = os.stat(path)
			files.append({"name": name, "size": st.st_size, "mtime": st.st_mtime})
	files.sort(key = lambda f: f["mtime"], reverse = True)
	disk = shutil.disk_usage(LOG_PATH)
	return jsonify(files=files, disk={"free": disk.free, "total": disk.total})

@app.route("/download/<path:file>")
def getPath(file):
	# send_from_directory refuses paths that escape LOG_PATH
	return send_from_directory(LOG_PATH, file, as_attachment=True)

@socketio.on('connect', namespace=SOCKET_NAMESPACE)
def handleConnect():
	# send the current state only to the client that just connected
	emit("state", server_not_interrupted)
	emit("str2str", proc is not None)
	emit("timesync", "pending" if time_sync_in_progress else time_is_synchronized)
	emit("profiles", profilesPayload())

@socketio.on('profile', namespace=SOCKET_NAMESPACE)
def handleProfile(name):
	global current_profile

	if server_not_interrupted:
		sendMessage("Stop the rover before changing the receiver profile")
	elif name not in [p["file"] for p in listProfiles()]:
		sendMessage("Unknown receiver profile: %s" % name)
	elif name != current_profile:
		current_profile = name
		try:
			saveProfile(name)
		except OSError as e:
			sendMessage("Could not save the receiver profile: %s" % e)
		sendMessage("Receiver profile set to %s" % PROFILE_NAMES.get(name, name))

	# always answer, so the panel shows the real selection
	socketio.emit("profiles", profilesPayload(), namespace=SOCKET_NAMESPACE)

@socketio.on('disconnect', namespace=SOCKET_NAMESPACE)
def handleDisconnect():
	print("Disconnected")

@socketio.on('str2str', namespace=SOCKET_NAMESPACE)
def handleStr2str():
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
	stopDisplay(["Shutting down...", "", "Wait 20 s, then", "unplug the power"])
	os.system("sudo shutdown -h now")

@socketio.on('cpu', namespace=SOCKET_NAMESPACE)
def handleCpu():
	socketio.emit("cpu", cpu.temperature, namespace=SOCKET_NAMESPACE)

@socketio.on('load', namespace=SOCKET_NAMESPACE)
def handleLoad():
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
	current_profile = loadProfile()

	green_led = LED(GREEN_LED_PIN_NUMBER)
	blue_led = LED(BLUE_LED_PIN_NUMBER)
	orange_led = LED(ORANGE_LED_PIN_NUMBER)

	if DISPLAY_ENABLED:
		socketio.start_background_task(displayLoop)

	try:
		# no reloader: it would run __main__ twice and claim the GPIO pins twice
		socketio.run(app, host = SOCKET_HOST, port = SOCKET_PORT,
			use_reloader = False, allow_unsafe_werkzeug = True)
	except KeyboardInterrupt:
		print("Server interrupted by user!")
	finally:
		stop()
		if not display_stopped:
			stopDisplay()
