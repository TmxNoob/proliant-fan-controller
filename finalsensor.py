#!/usr/bin/python3
import argparse
import os
from time import sleep,time
import configparser

class linuxMontior(object):
	"""docstring for linuxMontior"""
	def __init__(self):
		super(linuxMontior, self).__init__()
	def getTemps(self):
		temps = {}
		for tn,td in psutil.sensors_temperatures().items():
			for to in td:
				temps["local:%s:%s"%(tn,to.label)] = {"temp":to.current}
		return temps
class wmiMonitor(object):
	"""docstring for wmiMonitor"""
	def __init__(self):
		super(wmiMonitor, self).__init__()
		self.w = wmi.WMI(namespace="root\OpenHardwareMonitor")

	def getTemps(self):
		ohw = self.w.Sensor()
		temps = {}
		for s in ohw:
			if s.SensorType==u'Temperature':
				temps["local:%s"%s.Identifier] = {"temp":s.Value}
		return temps

class iloMonitor(object):
	"""docstring for iloMonitor"""
	def __init__(self, username, password, addr):
		super(iloMonitor, self).__init__()
		self.sess = r.Session()
		self.loginSucc = False
		self.iloAddr = addr
		loginresp = self.sess.post("%s/json/login_session"%self.iloAddr,data=j.dumps({"method":"login","user_login":username,"password":password}),verify=False)
		if "session_key" in loginresp.json().keys():
			self.session_key = loginresp.json()["session_key"]
			print("Login success!")
			self.loginSucc = True
		else:
			print("Login fail!")

	def logout(self):
		self.sess.post("%s/json/login_session"%self.iloAddr,data=j.dumps({"method":"logout","session_key":self.session_key}),verify=False)
		self.logged = False

	def getTemps(self):
		if not self.loginSucc:
			print("Not logged in!")
			return
		temps = {}
		for x in self.sess.get("%s/json/health_temperature?_=%i"%(self.iloAddr,int(time())*1000),verify=False).json()["temperature"]:
			temps["ilo%s"%x["label"]] = {"temp":x["currentreading"],"caution":x["caution"],"critical":x["critical"]}
		return temps


class serialFan(object):
	"""docstring for serialFan"""
	def __init__(self, serport=False):
		super(serialFan, self).__init__()
		self.fans = [15,15,15,15,15,15]
		self.ser = serial.Serial(serport,9600,timeout=1) if serport else False

	def setFan(self,fan,speed):
		self.fans[fan-1] = speed
		if self.ser:
			fpwm = int(speed/100*255)
			self.ser.write(b"s\n")
			self.ser.write(b"%i\n"%fan)
			self.ser.write(b"%i\n"%fpwm)
		else:
			print("Setting fan %i to %i%%"%(fan,speed))


	def getFan(self,fan):
		return self.fans[fan-1]		


if os.name=="nt":
	try:
		import wmi
	except ModuleNotFoundError:
		print("wmi not installed!")
		exit()
	temps = wmiMonitor()
else:
	try:
		import psutil
	except ModuleNotFoundError:
		print("'psutil' not installed!")
		exit()
	temps = linuxMontior()

try:
	import serial
except ModuleNotFoundError:
	print("pyserial not installed!")
	exit()

parser = argparse.ArgumentParser(description="Control HP fans over serial via custom controller")
parser.add_argument('--config', help="Load config", required=True)
parser.add_argument('--listsensors',action="store_true", help="List available sensors")
parser.add_argument('--debug',action="store_true", help="Enable debug mode (only for developing and testing)")
parser.add_argument('--setall',type=int, default=-1, help="Set all fans to this speed")
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)

if args.debug:
	serPort = False
else:
	serPort = config["General"]["serialPort"]

ilo = None
if config.getboolean("General","useILO"):
	ilo = iloMonitor(config["ILO"]["username"],config["ILO"]["password"],config["ILO"]["address"])

if args.listsensors:
	for tn,tv in temps.getTemps().items():
		print("'%s' : %.1f"%(tn,tv["temp"]))
	if ilo:
		print("Ilo configured, will now show all ILO sensors:")
		for tn,tv in ilo.getTemps().items():
			print("'%s' : %.1f"%(tn,tv["temp"]))
	exit()

sf = serialFan(serPort)

if args.setall != -1:
	if 0 > args.setall > 100:
		print("Fan speed has to be between 0-100")
		exit()
	for x in range(1,7):
		sf.setFan(x,args.setall)
		print("Set channel %i to %i%% speed"%(x,args.setall))
	exit()


def calcSpeed(temp,curve):
	largestfan = 0
	largesttemp = 0
	for ctemp,cfan in curve.items():
		if temp<ctemp: break
		largestfan = cfan
		largesttemp = temp
	return (largestfan,largesttemp)

#now the fun begins (actual fan logic)
wait = int(config["General"]["updateInterval"])


#load the profiles and add some extra runtime variables
profiles = {}
for p in config["General"]["profiles"].split(","):
	try:
		hys = int(config[p]["hysteresis"])
	except KeyError:
		hys = int(config["General"]["defaultHysteresis"])
	curve = {}
	for ct,cf in dict(config[config[p]["curve"]]).items(): curve[int(ct)] = int(cf)
	profiles[p] = {
		"fans":[int(x) for x in config[p]["fans"].split(",")],
		"sensors":config[p]["sensors"].split(","),
		"curve":curve,
		"hysteresis":hys,
		"lowerTemp":0,
		"lastSpeed":0
	}

while True:
	maxFanSpeeds = {1:0,2:0,3:0,4:0,5:0,6:0}
	curTemps = temps.getTemps()
	if ilo:
		curTemps = curTemps+ilo.getTemps()
	for pn,pd in profiles.items():
		maxtemp = max([curTemps[x]["temp"] for x in pd["sensors"]])
		spd,temp = calcSpeed(maxtemp,pd["curve"])
		if maxtemp < pd["lowerTemp"]:#temp has lowered under hysterisis
			profiles[pn]["lowerTemp"] = temp-pd["hysteresis"]
			profiles[pn]["lastSpeed"] = spd
		elif pd["lastSpeed"] < spd:#temp has risen over next point
				profiles[pn]["lowerTemp"] = temp-pd["hysteresis"]
				profiles[pn]["lastSpeed"] = spd
		for x in pd["fans"]:
			maxFanSpeeds[x] = max(maxFanSpeeds[x],profiles[pn]["lastSpeed"])
	for fn,fs in maxFanSpeeds.items():
		if args.debug
			print(maxFanSpeeds)
		else:
			sf.setFan(fn,fs)
	sleep(wait)


