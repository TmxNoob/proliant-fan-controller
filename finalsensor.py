#!/usr/bin/python3
import argparse
import os
from time import sleep,time

class linuxMontior(object):
	"""docstring for linuxMontior"""
	def __init__(self):
		super(linuxMontior, self).__init__()
	def getTemps(self):
		temps = {}
		for tn,td in psutil.sensors_temperatures().items():
			pass #TODO: implement dis shit
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
				temps[s.Identifier] = {"temp":s.Value}
		return temps
class iloMonitor(object):
	"""docstring for iloMonitor"""
	def __init__(self, username, password):
		super(iloMonitor, self).__init__()
		self.sess = r.Session()
		self.loginSucc = False
		loginresp = self.sess.post("%s/json/login_session"%ip,data=j.dumps({"method":"login","user_login":username,"password":password}),verify=False)
		if "session_key" in loginresp.json().keys():
			self.session_key = loginresp.json()["session_key"]
			print("Login success!")
			self.loginSucc = True
		else:
			print("Login fail!")

	def logout(self):
		self.sess.post("%s/json/login_session"%ip,data=j.dumps({"method":"logout","session_key":self.session_key}),verify=False)
		self.logged = False

	def getTemps(self):
		if not self.loginSucc:
			print("Not logged in!")
			return
		temps = {}
		for x in self.sess.get("%s/json/health_temperature?_=%i"%(ip,int(time())*1000),verify=False).json()["temperature"]:
			temps[x["label"]] = {"temp":x["currentreading"],"caution":x["caution"],"critical":x["critical"]}
		return temps

if os.name=="nt":
	print("We are running on windows, importing wmi")
	import wmi
	temps = wmiMonitor()
else:
	print("We are running on Linux, importing psutil :)")
	import psutil
	temps = None

try:
	import serial
except:
	print("pyserial not installed!")
	exit()


ip = "https://10.31.31.3"
serialport = "COM3"

class serialFan(object):
	"""docstring for serialFan"""
	def __init__(self, serport):
		super(serialFan, self).__init__()
		self.fans = [15,15,15,15,15,15]
		self.ser  = serial.Serial(serport,9600,timeout=1)

	def setFan(self,fan,speed):
		self.fans[fan-1] = speed
		fpwm = int(speed/100*255)
		self.ser.write(b"s\n")
		self.ser.write(b"%i\n"%fan)
		self.ser.write(b"%i\n"%fpwm)


	def getFan(self,fan):
		return self.fans[fan-1]		

parser = argparse.ArgumentParser(description="Control HP fans over serial via custom controller")
parser.add_argument('--ilouser', help="HP Ilo username")
parser.add_argument('--ilopass', help="HP Ilo username")
parser.add_argument('--mode',choices=["smart","simple"], default="smart", help="Simple: all fans same rpm")
parser.add_argument('--listsensors',action="store_true", help="List available sensors")
parser.add_argument('--static',type=int, default=-1, help="Set all fans to this speed")
args = parser.parse_args()
if args.ilouser and args.ilopass:
	print("importing ILO requirements...")
	import requests as r
	import json as j
	temps = iloMonitor(args.ilouser,args.ilopass)
if args.listsensors:
	print("Listing all sensors")
	for sn,st in temps.getTemps().items():
		print("%s - %iC"%(sn,st["temp"]))
	exit()


tempCurves = {
	"CPU": {
		50:10,
		60:20,
		65:25,
		70:30,	
		80:50
	},
	"GPU": {
		60:10,
		70:20,
		80:25,
		95:35
	},
	"HDD":{
		40:10,
		50:20,
		60:30
	}
}
sensors = {
	"/intelcpu/0/temperature/4":{"fans":[4,5,6],"curve":"CPU"},
	"/intelcpu/1/temperature/4":{"fans":[1,2,3],"curve":"CPU"},
	"/atigpu/0/temperature/0":{"fans":[4,5],"curve":"GPU"},
	"/hdd/0/temperature/0":{"fans":[1,2],"curve":"HDD"},
	"/hdd/1/temperature/0":{"fans":[1,2],"curve":"HDD"},
}

def curveFind(temp,curve):
	cs = 0
	for trigTemp,fanSpeed in tempCurves[curve].items():
		if trigTemp < temp:
			cs = fanSpeed
		else:
			return cs
	return cs

fans = {
	1:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
	2:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
	3:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
	4:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
	5:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
	6:{"lastSpeed":0,"tsChange":0,"tempAtTs":0,"nextSpeed":0},
}

waitDelay = 3
termalDelay = 5
sf = serialFan(serialport)
if args.static >= 0:
	try:
		while True:
			for x in range(6):
				sf.setFan(x,args.static)
	except KeyboardInterrupt:
		print("exiting")
	exit()
if args.mode=="smart":
	print("Staring in smart mode")



	t = temps.getTemps()
	for tn,td in t.items():
		try:
			sensor = sensors[tn]
			for fanNum in sensor["fans"]:
				fans[fanNum]["lastSpeed"] = max(fans[fanNum]["lastSpeed"],curveFind(td["temp"],sensor["curve"]))
		except KeyError:
			pass
	while True:
		lstart = time()
		t = temps.getTemps()
		for tn,td in t.items():
			try:
				sensor = sensors[tn]
				for fanNum in sensor["fans"]:
					fans[fanNum]["nextSpeed"] = max(fans[fanNum]["nextSpeed"],curveFind(td["temp"],sensor["curve"]))
			except KeyError:
				pass
		for fanNum in fans.keys():
			if fans[fanNum]["nextSpeed"] != fans[fanNum]["lastSpeed"]:
				if fans[fanNum]["tsChange"] == 0:
					fans[fanNum]["tsChange"] = time()
					fans[fanNum]["tempAtTs"] = td["temp"]
				else:
					if fans[fanNum]["tsChange"]+waitDelay<time() or (fans[fanNum]["tempAtTs"] - td["temp"] < -termalDelay and fans[fanNum]["nextSpeed"] < fans[fanNum]["lastSpeed"]):
						fans[fanNum]["lastSpeed"] = fans[fanNum]["nextSpeed"]
						fans[fanNum]["tsChange"] = 0
						fans[fanNum]["tempAtTs"] = 0
			else:
				fans[fanNum]["tsChange"] = 0
				fans[fanNum]["tempAtTs"] = 0
		for fanNum,fanData in fans.items():
			sf.setFan(fanNum,fanData["lastSpeed"])
			fans[fanNum]["nextSpeed"] = 0
		print([[x["lastSpeed"],x["lastSpeed"],x["tempAtTs"]] for x in fans.values()])
		sleep(max(1-(time()-lstart),0))

else:
	print("Starting in simple mode")