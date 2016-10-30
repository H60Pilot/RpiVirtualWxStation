#!/usr/bin/env python

import json
from datetime import datetime, timedelta

import sqlite3
import time
import urllib
import xmltodict

#####################################################################
#   ******** UPDATE These to match your configuration ************  #
#####################################################################

# http://www.aviationweather.gov and choose 4 letter ID for an airport near you
baroStation = 'KGON'

conn  = sqlite3.connect("/path/to/acurite.sqlite")

##########################################################################

### Rain Event Helpers

def convertToDateTime(dateString):
    return( datetime.strptime( dateString, '%Y-%m-%d %H:%M:%S'))

def convertDateToStr(dateObject):
    return( dateObject.strftime( '%Y-%m-%d %H:%M:%S'))

def getBaro ():
    baroUrl = "http://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString=" + baroStation + "&hoursBeforeNow=1&mostRecent=true"
    response = urllib.urlopen(baroUrl)
    metar = xmltodict.parse(response)['response']['data']['METAR']
    #print metar
    return metar['altim_in_hg']


def resetData(eventStartTime, rainAmount):
    if ((datetime.now() - convertToDateTime(eventStartTime)).days < 360):
        print('Resetting Data')
        sql = 'INSERT into rainEventData VALUES (\"' + eventStartTime + '\" ,' + str(rainAmount) + ')'
        print sql
        cursor.execute(sql)

def calcStormRain(beginTime):
        sql = 'SELECT min(rainCounter), max(rainCounter) FROM wxInfo WHERE insDate > \''  + beginTime + '\''
        cursor.execute(sql)
        rainData = cursor.fetchone()
        minCounter = rainData[0]
        maxCounter = rainData[1]
        counter = maxCounter - minCounter
        return counter + 1  #need to add 1 because you start with the new value, not the last counter

def clearLastEvent(startTime):
    if ((datetime.now() - convertToDateTime(startTime)).days < 360):
        print('Setting StartDate to old')
        oldTime = convertToDateTime(startTime) - timedelta(days = 365)
        sqlstr = 'startTime = "' + convertDateToStr(oldTime) + '"'
        sql = 'UPDATE lastEvent SET ' + sqlstr
        cursor.execute(sql)


#Set up the data connection
cursor = conn.cursor()

# Get last event information
sql = 'SELECT * from lastEvent'
cursor.execute(sql)
eventInfo = cursor.fetchone()
startTime = eventInfo[0]
lastEventTime = eventInfo[1]
startBaro = eventInfo[2]

# Determinie if the storm event is over
checkTime = datetime.now()
print ('Time is: {0}'.format(convertDateToStr(checkTime)))
print ('Last Event Time: {0}'.format(lastEventTime))
print ('{0} < {1}'.format(lastEventTime, convertDateToStr(checkTime - timedelta(hours=1))))

#check if 8 hrs has passed since it rained

if (convertToDateTime(lastEventTime) < (checkTime - timedelta(hours=8))):
        stormRain = calcStormRain(startTime) * 0.01
        resetData(startTime, stormRain)
        clearLastEvent(startTime)
        conn.commit()

# Or, check if 1 hr plus 0.03 increase in Barometer
elif (convertToDateTime(lastEventTime) < (checkTime - timedelta(hours=1))):
    print ('It has been at least an hour!')
    if (float(getBaro()) - float(startBaro) > 0.03 ):
        print ('And Baro is > 0.03!')
        stormRain = calcStormRain(startTime) * 0.01
        resetData(startTime, stormRain)
        clearLastEvent(startTime)
        conn.commit()

# storm event is defined as:
#   8 hrs since last UPDATE or
#   1 hr + 0.03 baro increase

# If the event is over
#  Record start event time and storm amount to rainEventData table
#  add 365 days to startTime in lastEvent table
