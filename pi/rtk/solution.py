"""Read rtkrcv's position solutions from one of its TCP server outputs.

rtkrcv writes solutions to outstr1/outstr2. When one of them is a TCP server
(tcpsvr) in llh or nmea format, find_output() finds it in the profile and
parse_llh() / parse_gga() turn its lines into dicts:

	{"lat", "lon", "h", "q", "quality", "ns", "sdn", "sde", "sdu",
	 "hacc", "hdop", "age", "ratio", "time"}

Fields a format doesn't carry are None (NMEA has no standard deviations,
llh has no HDOP).
"""

import math

# RTKLIB solution quality (Q column in llh)
QUALITY = {1: "FIX", 2: "FLOAT", 3: "SBAS", 4: "DGPS", 5: "SINGLE", 6: "PPP"}

# NMEA GGA fix quality -> RTKLIB quality
GGA_QUALITY = {1: 5, 2: 4, 4: 1, 5: 2}


def read_conf(path):
	"""key=value pairs of an RTKLIB options file, comments stripped."""
	opts = {}
	with open(path) as f:
		for line in f:
			if "=" not in line or line.lstrip().startswith("#"):
				continue
			key, value = line.split("=", 1)
			opts[key.strip()] = value.split("#", 1)[0].strip()
	return opts


def find_output(conf_path):
	"""(port, format, options) of the first tcpsvr output in llh or nmea
	format, preferring llh because it carries standard deviations. None if
	the profile has no such output."""
	opts = read_conf(conf_path)
	found = {}
	for n in (1, 2):
		if opts.get("outstr%d-type" % n) != "tcpsvr":
			continue
		fmt = opts.get("outstr%d-format" % n)
		port = opts.get("outstr%d-path" % n, "").rsplit(":", 1)[-1]
		if fmt in ("llh", "nmea") and port.isdigit() and fmt not in found:
			found[fmt] = int(port)
	for fmt in ("llh", "nmea"):
		if fmt in found:
			return found[fmt], fmt, {
				"degform": opts.get("out-degform", "deg"),
				"fieldsep": opts.get("out-fieldsep", ""),
			}
	return None


def _float(s):
	try:
		return float(s)
	except (TypeError, ValueError):
		return None


def _solution(lat, lon, h, q, ns, time, sdn=None, sde=None, sdu=None,
		age=None, ratio=None, hdop=None):
	hacc = math.hypot(sdn, sde) if sdn is not None and sde is not None else None
	return {
		"lat": lat, "lon": lon, "h": h,
		"q": q, "quality": QUALITY.get(q, "Q%d" % q),
		"ns": ns,
		"sdn": sdn, "sde": sde, "sdu": sdu, "hacc": hacc, "hdop": hdop,
		"age": age, "ratio": ratio,
		"time": time,
	}


def _dms(d, m, s):
	sign = -1 if d.startswith("-") else 1
	return sign * (abs(float(d)) + float(m) / 60 + float(s) / 3600)


def parse_llh(line, degform="deg", fieldsep=""):
	"""One line of RTKLIB llh output, or None for headers and junk.

	time(2) lat lon height Q ns sdn sde sdu sdne sdeu sdun age ratio
	(lat and lon take 3 fields each with out-degform=dms)"""
	line = line.strip()
	if not line or line.startswith("%"):
		return None
	if fieldsep:
		t = [x.strip() for x in line.split(fieldsep) if x.strip()]
		# the date and time are separated by a space even with a separator
		if len(t) and " " in t[0]:
			t = t[0].split() + t[1:]
	else:
		t = line.split()

	try:
		time = t[0] + " " + t[1]
		if degform == "dms":
			lat, lon, i = _dms(*t[2:5]), _dms(*t[5:8]), 8
		else:
			lat, lon, i = float(t[2]), float(t[3]), 4
		h = float(t[i])
		q = int(t[i + 1])
		ns = int(t[i + 2])
	except (IndexError, ValueError):
		return None

	rest = [_float(x) for x in t[i + 3:i + 11]] + [None] * 8
	sdn, sde, sdu, _, _, _, age, ratio = rest[:8]
	return _solution(lat, lon, h, q, ns, time, sdn, sde, sdu, age, ratio)


def _nmea_checksum_ok(line):
	if "*" not in line:
		return True  # checksum is optional
	body, _, given = line[1:].partition("*")
	calc = 0
	for c in body:
		calc ^= ord(c)
	try:
		return calc == int(given[:2], 16)
	except ValueError:
		return False


def _nmea_deg(value, hemi, width):
	if not value:
		return None
	deg = float(value[:width]) + float(value[width:]) / 60
	return -deg if hemi in ("S", "W") else deg


def parse_gga(line):
	"""A $xxGGA sentence, or None for other sentences and junk."""
	line = line.strip()
	if not line.startswith("$") or line[3:6] != "GGA" or not _nmea_checksum_ok(line):
		return None
	f = line.split("*")[0].split(",")
	try:
		gga_q = int(f[6] or 0)
		if gga_q == 0:
			return None  # no fix
		lat = _nmea_deg(f[2], f[3], 2)
		lon = _nmea_deg(f[4], f[5], 3)
		if lat is None or lon is None:
			return None
		h = (_float(f[9]) or 0) + (_float(f[11]) or 0)   # ellipsoidal = MSL + geoid
		ns = int(f[7] or 0)
	except (IndexError, ValueError):
		return None
	time = "%s:%s:%s" % (f[1][0:2], f[1][2:4], f[1][4:]) if len(f[1]) >= 6 else f[1]
	return _solution(lat, lon, h, GGA_QUALITY.get(gga_q, 5), ns, time,
		age=_float(f[13]) if len(f) > 13 else None, hdop=_float(f[8]))


def parse(line, fmt, options):
	if fmt == "llh":
		return parse_llh(line, options.get("degform", "deg"), options.get("fieldsep", ""))
	return parse_gga(line)
