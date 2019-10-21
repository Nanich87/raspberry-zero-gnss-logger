#!/bin/python

import RPi.GPIO as GPIO
import os

import sys
import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError

TOKEN = ''
LOCALFILE = '/home/pi/rtk/rtk.log'
BACKUPPATH = '/RTKLIB/rtk.log'

gpio_pin_number=21

GPIO.setmode(GPIO.BCM)
GPIO.setup(gpio_pin_number, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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

try:
	#print("Waiting for shutdown command...")
	GPIO.wait_for_edge(gpio_pin_number, GPIO.FALLING)

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
		print("Done!")

	os.system("sudo shutdown -h now")
except:
    	pass

GPIO.cleanup()
