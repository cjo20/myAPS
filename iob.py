##import random 
import calendar
from datetime import datetime, date, time

import csv
# 1.5 and 7.5
patientData = {}
patientData['delay'] = 15 * 60
patientData['carbsPerHour'] = 33
patientData['isf'] = 1.8
patientData['carbsPerUnit'] = 9
patientData['dia'] = 5
target = 6.5

def getCSF( pData ):
	return pData['isf'] / pData['carbsPerUnit']

def getCarbsPerMinute( pData ):
	return pData['carbsPerHour'] / 60.0

def carbsAbsorbed( nextFreeTime, atTime, record):
	carbsPerMinute = getCarbsPerMinute(patientData)
	result = {}
	result['carbs'] = 0
	result['nextFreeTime'] = nextFreeTime

	absorbtionStart = max(record['time'] + patientData['delay'], nextFreeTime)

	if (absorbtionStart > atTime):
		return result

	timeSinceAbsorbStarted = (atTime - absorbtionStart) / 60
	carbsAbsorbed = min(record['dose'], timeSinceAbsorbStarted * getCarbsPerMinute(patientData))
	if (carbsAbsorbed == record['dose']):
		result['nextFreeTime'] = absorbtionStart + ((60 * record['dose']) / carbsPerMinute) 
	else:
		result['nextFreeTime'] = absorbtionStart + ((60 * carbsAbsorbed) / carbsPerMinute)

	result['carbs'] = carbsAbsorbed

	return result


def getCarbsAbsorbedSince(startTime, atTime, records):
	lastTime = 0
	carbsOB = 0
	for x in records:
		if (x['type'] != 2):
			continue

		result = carbsAbsorbed(lastTime, atTime, x)
		result2 = carbsAbsorbed(lastTime, startTime, x)
		lastTime = result['nextFreeTime']
		carbsOB = carbsOB + result['carbs'] - result2['carbs']
	return carbsOB

def dia6Hours(t):
	result = -1.493e-10*pow(t,4)+1.413e-7*pow(t, 3) - 4.095e-5*pow(t, 2)+6.365e-4*t+0.997
	if result < 0:
		return 0
	return result

def dia5Hours(t):
	result = -2.95e-10*pow(t,4)+2.32e-7*pow(t,3)-5.55e-5*pow(t,2)+4.49e-4*t+0.993
	if result < 0:
		return 0
	return result 

def dia4Hours( t ):
	result =  -3.31e-10*pow(t,4) + 2.53e-7*pow(t,3) - 5.51e-5*pow(t,2)-9.086e-4*t+0.9995
	if result < 0:
		return 0

	return result

def GetInsulinRemaining(t, dia):
	if dia == 4:
		return dia4Hours(t)
	elif dia == 5:
		return dia5Hours(t)
	elif dia == 6:
		return dia6Hours(t)
	else:
		return 0

def insulinRemainingFromTreatment( record, atTime ):

	if ( record['type'] != 0):
		return 0

	if (record['time'] > atTime):
		return 0
	formattedTime = datetime.utcfromtimestamp(record['time']).strftime('%Y-%m-%d %H:%M:%S')
	timeAgoTuple = datetime.now().timetuple()
	timeAgo = atTime - record['time']
	timeAgoMins = timeAgo / 60
	insulinRemaining = GetInsulinRemaining(timeAgoMins, patientData['dia']) * record['dose']
	return insulinRemaining


def getInsulinUsedSince(startTime, atTime, records):
	iOB = 0
	for x in records:

		if (x['type'] != 0):
			continue

		startingDose = x['dose']
		if (startTime > x['time']):
			startingDose = insulinRemainingFromTreatment(x, startTime)

		if (atTime < x['time']):
			continue
		currentDose = insulinRemainingFromTreatment(x, atTime)
		iOB = iOB + startingDose - currentDose
	return iOB


def FindLatestBG ( records ):
	result = {'lastTime': 0, 'lastBG': 0}
	for k in treatments:
		if (k['type'] == 1 and k['time'] > result['lastTime']):
			result['lastTime'] = k['time']
			result['lastBG'] = k['dose']

	return result


def getActiveAtTime(atTime, records):
	totalActive = 0
	for x in records:
		if (x['type'] != 0):
			continue

		if (x['time'] >= atTime):
			continue

		timeSinceStart = atTime - x['time']
		timeSinceStart = timeSinceStart / 60
		
		totalActive = totalActive + ((GetInsulinRemaining(timeSinceStart, patientData['dia']) - GetInsulinRemaining(timeSinceStart + 1, patientData['dia'])) * x['dose'])
	return totalActive


def getIOBatTime( time, records):
	totalIOB = 0
	for x in records:
		totalIOB = insulinRemainingFromTreatment(x, time) + totalIOB
	return totalIOB

def PredictIOB ( startingTime, records):
	target = open("iob.csv", 'w')
	target.truncate()

	for i in xrange(-60, 360):
		seconds = i * 60
		iob = getIOBatTime(startingTime + seconds, records)
		active =  getActiveAtTime(startingTime + seconds, records)
		currentTime = startingTime + seconds
		formattedTime = datetime.utcfromtimestamp(currentTime).strftime('%H:%M:%S')
		target.write("%s,%s," % (formattedTime, active))
		target.write("%s" % iob)
		target.write("\n")

	target.close()

# Predicts what is going to happen to BG over the next 6 hours
def PredictBGCurve( startingBG, startingTime, isf, records ):

	iobLeft = getIOBatTime(startingTime, records)

	target = open("predict.csv", 'w')
	target.truncate()
	target.write("ISF,%s\n" % patientData['isf'])
	target.write("carbsPerU,%s\n" % patientData['carbsPerUnit'])
	target.write("CSF,%s\n" % getCSF(patientData))
	target.write("Delay,%s\n" % (patientData['delay']/60))
	target.write("CarbsPerHour,%s\n" % patientData['carbsPerHour'])
	for i in xrange(0, 480):
		seconds = i * 60;
		iob = getIOBatTime(startingTime + seconds, records)
		iobUsed = getInsulinUsedSince(startingTime, startingTime + seconds, records)
#		print "iob: %s, seconds %d" % (iobUsed, seconds)
		cob = getCarbsAbsorbedSince(startingTime, startingTime + seconds, records)
#		print "cob: %s, seconds %d" % (cob, seconds)
		iobDiff = iobLeft - iob
		bgDrop = (iobUsed * patientData['isf']) - (cob * getCSF(patientData))
#		print "iobDiff: %.1f, cob: %.1f, bgDrop: %.1f" % (iobDiff, cob, bgDrop)
		newBG = startingBG - bgDrop		
		currentTime = startingTime + seconds
#		print "At time %d BG is %f" % (startingTime + seconds, newBG)
		formattedTime = datetime.utcfromtimestamp(currentTime).strftime('%H:%M:%S')

		target.write("%s" % formattedTime)
		target.write(",")
		target.write("%s" % newBG)
		target.write("\n")

	target.close()


treatments = []

def getRecordsFromFile():
	for row in csv.reader(open("data.csv", 'rb')):
		treatment = {}
		if len(row) == 0:
			continue

		if row[0].startswith("#"):
			continue
		treatment['type'] = int(row[1])
		treatment['dose'] = float(row[2])
		treatment['time'] = calendar.timegm(datetime.strptime(row[0], "%Y-%m-%d %H:%M").timetuple())
#		print "Time: %s, Type: %s, Dose: %s\n" % (row[0], row[1], row[2])
#		print treatment
		treatments.append(treatment)


getRecordsFromFile()

totalIOB = 0

mostRecent = FindLatestBG(treatments)
print mostRecent
totalIOB = getIOBatTime(mostRecent['lastTime'], treatments)
#for k in treatments:
#	totalIOB = totalIOB + insulinRemainingFromTreatment(k, mostRecent['lastTime'])

usedIOB = getInsulinUsedSince(mostRecent['lastTime'],mostRecent['lastTime'] + 5*60*60, treatments)
absorbedCarbs = getCarbsAbsorbedSince(mostRecent['lastTime'],mostRecent['lastTime'] + 5*60*60, treatments)
expectedDrop = usedIOB * patientData['isf'] - (absorbedCarbs * getCSF(patientData))
expectedBG = mostRecent['lastBG'] - expectedDrop
bgDiff = expectedBG - target
suggestedDose = bgDiff /  patientData['isf']
print "Based on BG at %s" % datetime.utcfromtimestamp(mostRecent['lastTime']).strftime('%Y-%m-%d %H:%M:%S')
print "IOB: %fu" % totalIOB
print "Expected Drop: %.2f" % expectedDrop
print "Expected BG: %.2f" % (mostRecent['lastBG'] - expectedDrop)
print "Recommend: %.2fu" % suggestedDose

timeAgoTuple = datetime.now().timetuple()

currentIOB = getIOBatTime(calendar.timegm(datetime.now().timetuple()), treatments)
currentIOB = getInsulinUsedSince(mostRecent['lastTime'],calendar.timegm(datetime.now().timetuple()), treatments)
currentCOB = getCarbsAbsorbedSince(mostRecent['lastTime'], calendar.timegm(datetime.now().timetuple()), treatments)
#usedIOB = totalIOB - currentIOB
currentDrop = currentIOB *  patientData['isf'] - currentCOB * getCSF(patientData)
currentBG = mostRecent['lastBG'] - currentDrop
print "Estimated BG at %s:  %.1f" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), currentBG)
print "%.2fu still active" % getIOBatTime(calendar.timegm(datetime.now().timetuple()), treatments)


PredictBGCurve(mostRecent['lastBG'], mostRecent['lastTime'], patientData['isf'], treatments)
PredictIOB(mostRecent['lastTime'], treatments)
print "Carbs: %s" % getCarbsAbsorbedSince(mostRecent['lastTime'], calendar.timegm(datetime.now().timetuple()), treatments)
