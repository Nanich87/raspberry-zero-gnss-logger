"""Status display for a small SSD1306 OLED (128x32 or 128x64) on I2C.

Talks to the display directly over I2C, so the only dependencies are
Pillow and smbus2 (or the older smbus). If the display or the libraries
are missing, every method quietly does nothing and the server keeps running.
"""

from threading import RLock

try:
	from smbus2 import SMBus
except ImportError:
	try:
		from smbus import SMBus
	except ImportError:
		SMBus = None

try:
	from PIL import Image, ImageDraw, ImageFont
except ImportError:
	Image = None

_CMD = 0x00    # control byte: commands follow
_DATA = 0x40   # control byte: display data follows
_CHUNK = 31    # SMBus block writes take at most 32 bytes, one is the control byte

class StatusDisplay:
	def __init__(self, bus=1, address=0x3C, width=128, height=32):
		self.bus_number = bus
		self.address = address
		self.width = width
		self.height = height
		self.pages = height // 8
		self.bus = None
		self.error = None   # last error, reported once
		self.lock = RLock()  # refresh loop and shutdown may draw at the same time

		if SMBus is None or Image is None:
			self.error = "display disabled: install python3-pil and python3-smbus (or smbus2)"
			return

		self.image = Image.new("1", (width, height))
		self.draw = ImageDraw.Draw(self.image)
		# the classic 6x11 bitmap font: 21 characters per line on 128 px.
		# Pillow >= 10.1 returns a scalable font from load_default(), so ask
		# for the bitmap one explicitly there.
		if hasattr(ImageFont, "load_default_imagefont"):
			self.font = ImageFont.load_default_imagefont()
		else:
			self.font = ImageFont.load_default()

		# The default font leaves empty rows above capitals; shift text up so
		# four lines fit in 32 px (descenders may touch the next line)
		probe = Image.new("1", (width, 16))
		ImageDraw.Draw(probe).text((0, 0), "IP 0", font=self.font, fill=255)
		bbox = probe.getbbox()
		self.y_offset = -bbox[1] if bbox else 0

	@property
	def available(self):
		return self.bus is not None

	def _command(self, *cmds):
		self.bus.write_i2c_block_data(self.address, _CMD, list(cmds))

	def _begin(self):
		"""Open the bus and initialise the display. Returns True on success."""
		if SMBus is None or Image is None:
			return False
		try:
			self.bus = SMBus(self.bus_number)
			self._command(
				0xAE,                                   # display off
				0xD5, 0x80,                             # clock divide
				0xA8, self.height - 1,                  # multiplex ratio
				0xD3, 0x00,                             # display offset
				0x40,                                   # start line 0
				0x8D, 0x14,                             # charge pump on
				0x20, 0x00,                             # horizontal addressing
				0xA1, 0xC8,                             # flip so the pins are on top
				0xDA, 0x02 if self.height == 32 else 0x12,  # COM pins
				0x81, 0x8F if self.height == 32 else 0xCF,  # contrast
				0xD9, 0xF1,                             # pre-charge
				0xDB, 0x40,                             # VCOMH
				0xA4,                                   # show RAM contents
				0xA6,                                   # normal (not inverted)
				0x2E,                                   # no scrolling
				0xAF,                                   # display on
			)
			self.error = None
			self._show([])
			return True
		except OSError as e:
			self._close()
			self.error = "display not found on I2C bus %d at 0x%02X: %s" % (self.bus_number, self.address, e)
			return False

	def _close(self):
		if self.bus is not None:
			try:
				self.bus.close()
			except OSError:
				pass
		self.bus = None

	def _flush(self):
		pixels = self.image.load()
		buf = []
		for page in range(self.pages):
			for x in range(self.width):
				byte = 0
				for bit in range(8):
					if pixels[x, page * 8 + bit]:
						byte |= 1 << bit
				buf.append(byte)

		self._command(0x21, 0, self.width - 1, 0x22, 0, self.pages - 1)
		for i in range(0, len(buf), _CHUNK):
			self.bus.write_i2c_block_data(self.address, _DATA, buf[i:i + _CHUNK])

	def _show(self, lines):
		"""Draw up to height/8 lines of text. Returns False if the display failed."""
		if self.bus is None:
			return False
		self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
		for row, text in enumerate(lines[:self.pages]):
			self.draw.text((0, row * 8 + self.y_offset), text, font=self.font, fill=255)
		try:
			self._flush()
			return True
		except OSError as e:
			self._close()
			self.error = "display write failed: %s" % e
			return False

	def clear(self):
		self.show([])

	def begin(self):
		"""Open the bus and initialise the display. Returns True on success."""
		with self.lock:
			return self._begin()

	def show(self, lines):
		"""Draw up to height/8 lines of text. Returns False if the display failed."""
		with self.lock:
			return self._show(lines)

	def off(self):
		"""Blank the display and turn it off (used on shutdown)."""
		with self.lock:
			self._off()

	def _off(self):
		"""Blank the display and turn it off (used on shutdown)."""
		if self.bus is None:
			return
		try:
			self._show([])
			self._command(0xAE)
		except OSError:
			pass
		self._close()
