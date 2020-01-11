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

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError

RTKLIB_PATH = "/home/pi/RTKLIB"
CONFIG_NAME = "/home/pi/f9p_navi.conf"
#CONFIG_NAME = "/home/pi/6m_navi.conf"
LOG_PATH = '/home/pi/log/'
DROPBOX_PATH = '/TimeMark/'

SERIAL_PORT_BAUD_RATE = 460800

CAMERA_PIN_NUMBER = 20
SHUTDOWN_PIN_NUMBER = 21
GREEN_LED_PIN_NUMBER = 17
BLUE_LED_PIN_NUMBER = 27
ORANGE_LED_PIN_NUMBER = 22

TOKEN = ''

time_mark_log_file = time.strftime("%Y-%m-%d-%H-%M-%S") + '.log';
time_mark_log_path = os.path.join(LOG_PATH, time_mark_log_file)

logging.basicConfig(level=logging.INFO,filename=time_mark_log_path,format='%(asctime)s %(message)s')

semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = True
time_is_synchronized = False

def backupDropbox():
	files = os.listdir(LOG_PATH)
	files.sort()
	for file in files:
		path = os.path.join(LOG_PATH,file)
		uploadFile(file,path)

def backupExternalStorage():
	files = os.listdir(LOG_PATH)
	files.sort()
	for file in files:
		src = os.path.join(LOG_PATH, file)
		dst = os.path.join('/media/usb/', file)

		copyfile(src, dst)
		print(file)

def uploadFile(file,path):
	dropbox_path = os.path.join(DROPBOX_PATH, file)

	with open(path, 'rb') as f:
		print("Uploading " + file + " to Dropbox as " + dropbox_path + "...")

		try:
				dbx.files_upload(f.read(), dropbox_path, mode=WriteMode('add'))
		except ApiError as err:
				if (err.error.is_path() and err.error.get_path().reason.is_insufficient_space()):
						print("ERROR: Cannot back up; insufficient space.")
				elif err.user_message_text:
						print(err.user_message_text)
				else:
						print(err)

def saveMark():
	semaphore.acquire()

	rtk.getMark()
	print(rtk.mark)
	logging.info(rtk.mark)

	semaphore.release()

def setCorrectTime():
	if not gps_time.time_synchronised_by_ntp():
		print("Time is not synced by NTP")

		gps_time.set_gps_time("/dev/serial0", SERIAL_PORT_BAUD_RATE)

		global time_is_synchronized
		time_is_synchronized = True

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
	shutdown_button = Button(SHUTDOWN_PIN_NUMBER)

	green_led = LED(GREEN_LED_PIN_NUMBER)
	blue_led = LED(BLUE_LED_PIN_NUMBER)
	orange_led = LED(ORANGE_LED_PIN_NUMBER)

	try:
		camera_button = Button(CAMERA_PIN_NUMBER)
		camera_button.when_pressed = saveMark

		blue_led.blink()

		time_thread = Thread(target = setCorrectTime)
		time_thread.start()

		while time_is_synchronized == False:
			time.sleep(5)

		blue_led.on()

		res = launchRover(CONFIG_NAME)
		if res == 1:
			startRover()

			green_led.on()
		else:
			orange_led.on()

		shutdown_button.wait_for_press()

		print("Shutdown button pressed...")

		green_led.blink()

		if (len(TOKEN) > 0):
			print("Creating a Dropbox object...")
			dbx = dropbox.Dropbox(TOKEN)

			user_is_authorized = False

			try:
				dbx.users_get_current_account()

				user_is_authorized = True

			except AuthError:
				print("Invalid access token; try re-generating an access token from the app console on the web.")

			if user_is_authorized == True:
				backupDropbox();

				print("Done uploading to Dropbox!")

			else:
				print("User is not authorized!")
				orange_led.blink()

		green_led.off()

	except KeyboardInterrupt:
		print("Server interrupted by user!")

	finally:
		stopRover()
		shutdownRover()

		time.sleep(5)

		blue_led.blink()
		print("Copying files to USB...")

		try:
			backupExternalStorage()
		except:
			print("Error occured while trying to copy log files to external storage device!")

		blue_led.off()

		os.system("sudo shutdown -h now")