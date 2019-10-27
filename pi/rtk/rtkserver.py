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

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError

RTKLIB_PATH = "/home/pi/RTKLIB"
CONFIG_NAME = "/home/pi/f9p_navi.conf"
CAMERA_LOG_PATH = "/home/pi/rtk/rtk.log"

CAMERA_PIN_NUMBER = 13
SHUTDOWN_PIN_NUMBER = 21
GREEN_LED_PIN_NUMBER = 17

TOKEN = ''
LOCALFILE = '/home/pi/rtk/rtk.log'
BACKUPPATH = '/RTKLIB/rtk.log'

logging.basicConfig(level=logging.INFO,filename=CAMERA_LOG_PATH,format='%(asctime)s %(message)s')

semaphore = Semaphore()
rtk = RtkController(RTKLIB_PATH)
server_not_interrupted = True

def backup():
	with open(LOCALFILE, 'rb') as f:
		# We use WriteMode=overwrite to make sure that the settings in the file
		# are changed on upload

		print("Uploading " + LOCALFILE + " to Dropbox as " + BACKUPPATH + "...")

		try:
			dbx.files_upload(f.read(), BACKUPPATH, mode=WriteMode('overwrite'))
		except ApiError as err:
			# This checks for the specific error where a user doesn't have
			# enough Dropbox space quota to upload this file
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

	try:
		camera_button = Button(CAMERA_PIN_NUMBER)
		camera_button.when_pressed = saveMark

		res = launchRover(CONFIG_NAME)
		if res == 1:
			startRover()
			green_led.on()

		shutdown_button.wait_for_press()
		green_led.blink()

		if (len(TOKEN) > 0):
			# Create an instance of a Dropbox class, which can make requests to the API.
			print("Creating a Dropbox object...")
			dbx = dropbox.Dropbox(TOKEN)

			# Check that the access token is valid
			try:
				dbx.users_get_current_account()
			except AuthError:
				print("ERROR: Invalid access token; try re-generating an access token from the app console on the web.")

			backup();
			green_led.off()

			print("Done!")

	except KeyboardInterrupt:
		print("Server interrupted by user!")

	finally:
		stopRover()
		shutdownRover()

	os.system("sudo shutdown -h now")

