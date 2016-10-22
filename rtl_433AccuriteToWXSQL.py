# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#
#   rtl_433_wrapper.py
#
#   Wrapper script for executing "rtl_433" and processing the output as it occurs in realtime.
#   As currently written it works with the "Aculink 5n1" weather station.
#
#   >>>---> Changes to handle other makes/models will likely be necessary, possibly to the rtl_433 source as well because ouputting data
#           as JSON hasn't been implemented in  all of the protocol handlers :-/
#
#   The goal is to be able to use "rtl_433" unmodified so that is easy to stay current as support for additional devices/protocols are added.
#   Note: To make this "real" some refactoring of the rtl_433 source will be needed to add consistent support for JSON across the various protocol handlers.
#
#   Modified to read Temp, Humidity, Wind Speed and Direction and insert them into a table.  This is done x times then
#   Wind Speed and Direction are averaged and all information is written to the KWReadings.txt for PHP Weather
#
# --------------------------------------------------------------------------------------------------------------------------------------------------------------
import sys
import os
from subprocess import PIPE, Popen, STDOUT
from threading  import Thread
import json
from datetime import datetime
import datetime as dt
import sqlite3
import time
import math
import urllib
import xmltodict
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#####################################################################
#   ******** UPDATE These to match your configuration ************  #
#####################################################################

# http://www.aviationweather.gov and choose 4 letter ID for an airport near you
baroStation = 'KGON'

sqliteDB = "/path/to/acurite.sqlite"

cmd = [ '/usr/local/bin/rtl_433', '-F', 'json', '-R', '9'] #use 12 for OS
##########################################################################

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#   A few helper functions...
def tempCtoF( tempC):
    return(( str( round( float( tempC) * 1.8) + 32)))

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def speedKtoM( speedK):
    return( str( int( round( float( speedK) *  0.6214))))

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def nowStr():
    return( dt.datetime.now().strftime( '%Y-%m-%d %H:%M:%S'))
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# based upon http://www.laketyersbeach.net.au/windaveraging.html and using Radian math and sin/cos averages.
def CalcAvgWind( myquadrant):
    #print 'myquadrant = ' + str(myquadrant[0])
    sumSin=0.0
    sumCos=0.0
    sumDir=0.0
    pi=math.pi
    pi8=math.pi/8.0
    #create a list of the tuple (dir,) of myquadrant
    listarray = [v[0] for v in myquadrant]
    for i in range(0,len(listarray)-1):
      sumDir=sumDir+listarray[i]
      sumSin=sumSin+math.sin(listarray[i]*pi8)
      sumCos=sumCos+math.cos(listarray[i]*pi8)
    avSin=sumSin/len(listarray)
    avCos=sumCos/len(listarray)
    avDir=(sumDir/len(listarray))

    windQuadrant = str(((int(math.atan2(avSin,avCos)/pi8))+16)%16)

    return( windQuadLookup[windQuadrant])

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
stripped = lambda s: "".join(i for i in s if 31 < ord(i) < 127)

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#  LOOKUPS
#   Mapping the Aculink 5n1 raw RF wind direction values to integer quadrants for averaging...
#   > pulled from "aculink.c"
windDirLookup = {
        '315.0':    '14',
        '247.5':    '11',
        '292.5':    '13',
        '270.0':    '12',
        '337.5':    '15',
        '225.0':    '10',
        '0.0':      '0',
        '202.5':    '9',
        '67.5':     '3',
        '135.0':    '6',
        '90.0':     '4',
        '112.5':    '5',
        '45.0':     '2',
        '157.5':    '7',
        '22.5':     '1',
        '180.0':    '8'
    }
# maps the integer quadrants to Compass Rose Direction
windQuadLookup = {
        '14':    'NW',
        '11':    'WSW',
        '13':    'WNW',
        '12':    'W',
        '15':    'NNW',
        '10':    'SW',
        '0':      'N',
        '9':    'SSW',
        '3':     'ENE',
        '6':    'SE',
        '4':     'E',
        '5':    'ESE',
        '2':     'NE',
        '7':    'SSE',
        '1':     'NNE',
        '8':    'S'
    }

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

writeToDB = True
hxTablename = 'wxInfo'

#   Create our database & table if it doesn't already exist...
if ( writeToDB):
    # Connecting to the database file
    conn = sqlite3.connect( sqliteDB)
    c = conn.cursor()

    if ( 1 == 0):   #   Set to "1 == 1" to drop an existing table...
        sqlStmt = 'DROP TABLE IF EXISTS ' + hxTablename + ';'
        c.execute( sqlStmt)
        conn.commit()

    sqlStmt = """
    CREATE TABLE IF NOT EXISTS wxInfo (
        insDate                 datetime,
        windSpeed               real,
        windDirection           real,
        temp                    real,
        humidity                real,
        rainGauge               real,
        rainCounter             int
    );
    """
    #   print 'sqlStmt = "' + sqlStmt + '"'
    c.execute( sqlStmt)
    conn.commit()

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

#   We're using a queue to capture output as it occurs
try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x
ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(src, out, queue):
    for line in iter(out.readline, b''):
        queue.put(( src, line))
    out.close()

#   Create our sub-process...
#   Note that we need to either ignore output from STDERR or merge it with STDOUT due to a limitation/bug somewhere under the covers of "subprocess"
#   > this took awhile to figure out a reliable approach for handling it...
p = Popen( cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, close_fds=ON_POSIX)
q = Queue()

t = Thread(target=enqueue_output, args=('stdout', p.stdout, q))

t.daemon = True # thread dies with the program
t.start()

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

record = {}
pulse = 0
rainDataCounter = 1000

while 1==1:
    #   Other processing can occur here as needed...

    try:
        src, line = q.get(timeout = 1)
    except Empty:
        pulse += 1
    else: # got line
        pulse -= 1
        #   See if the data is something we need to act on...
        if ( line.find( 'OS') !=-1):
            # we have the Oregon Scientific data
            # 2016-08-09 14:34:08 	:	OS :	THGR122N
	        #      House Code:	 244
	        #      Channel:	 1
	        #      Battery:	 OK
	        #      Temperature:	 32.20 C
	        #      Humidity:	 7 %

# {"time" : "2016-08-20 20:36:16", "brand" : "OS", "model" : "THGR122N", "id" : 244, "channel" : 1, "battery" : "OK", "temperature_C" : 24.400, "humidity" : 42}

            # Clean up the data to only include numbers
            line = stripped( line)
            line = line.replace( ' C', '') # remove the Celceus
            line = line.replace( '%', '')  # remove the %

            # parse the data from json to a python dictionary object
            OSdata = json.loads( line)
            mqt = tempCtoF(OSdata['temperature_C'])

        if ( line.find( 'wind') != -1):
            #   Sample data for our two message formats...
            #   wind speed: 3 kph, wind direction: 180.0[degree], rain gauge: 0.00 in.
            #   wind speed: 4 kph, temp: 52.5[degree] F, humidity: 51% RH

            #   Remove the [degree] character as well as Unit Of Measure indicators...
            line = stripped( line)
            line = line.replace( ' F', '')
            line = line.replace( '% RH', '')
            line = line.replace( ' kph', '')
            line = line.replace( ' in.', '')

            #   Add a timestamp & tweak the formatting a bit so we have valid JSON...
            line = 'timestamp: ' + nowStr() + ', ' + line
            line = '{"' + line + '"}'
            line = line.replace( ', ', '","')
            line = line.replace( ': ', '":"')

            #   Although data comes in as two rows I wanted to store it as a single row in the DB.
            #   As a result we need to piece it together to get a single record before we process it further...

            #   At this point our data is a JSON string...
            #   Convert our JSON string to a Python object, then move the data into a dictionary as we get each row...
            data = json.loads( line)

            for item in data:
                record[ item] = data[ item]

            #   When we have "rain gauge" and "temp" in our dictionary we know we have processed two rows & now have a complete record...
            if (( 'rain gauge' in record) and ( 'temp' in record)):
                #   Touch up our data- UoM, formatting, etc...
                record[ 'wind speed'] = speedKtoM( record[ 'wind speed'])
                record[ 'temp'] = str( int( round( float( record[ 'temp']))))
                record[ 'wind direction'] = windDirLookup[ record[ 'wind direction']]

                sys.stdout.write( nowStr() + ' - Wind Speed: ' + record[ 'wind speed'] + ', Wind Dir: "' + windQuadLookup[record[ 'wind direction']] + '", Temp: ' + record[ 'temp'] + ', Humidity: ' + record[ 'humidity'] + ', Rain: ' + record[ 'rain gauge']+ ', Counter:  ' + record['Rain Counter']+ '\n')

                #   Insert data into the DB...
                sqlStr = '"' + record[ 'timestamp'] + '", ' + record[ 'wind speed'] + ', "' + record[ 'wind direction'] + '", ' + record[ 'temp'] + ', ' + record[ 'humidity'] + ', ' + record[ 'rain gauge'] + ', ' + record['Rain Counter']
                sqlStmt = 'insert into ' + hxTablename + ' values ( ' + sqlStr + ')'
                #print 'sqlStmt:', sqlStmt
                try:
                    c.execute( sqlStmt)

                except sqlite3.IntegrityError:
                    True
                    print '\t      >>>----> ERROR: PK violation...'

                if (rainDataCounter < record['Rain Counter']):
                # Grab the event data from lastEvent and compare the dates to see if you're in an event or not
                    sql = ' SELECT startTime from lastEvent'
                    c.execute(sql)
                    eventData = c.fetchone()
                    #convert returned date string to date object
                    eventStartTime = convertToDateTime(eventData[0])

                    #if the date spread is at least a year, then we have a new event
                    #NOTE: I randomly will take today and subtract 365 days to reset events in CRON Job.

                    if ((convertToDateTime(record['timestamp']) - eventStartTime ).days > 364):
                        #get the latest Barometer
                        barometer = round(float(getBaro())*100)/100
                        #update startTime and startBaro based upon downloaded startTime
                        sqlstr = 'startTime = "' + record['timestamp'] + '",startBaro = ' + str(barometer) + ' WHERE startTime = "' + convertDateToStr(eventStartTime) + '"'
                        sql = 'UPDATE lastEvent SET ' + sqlstr
                        c.execute(sql)

                    else:
                        #update updateTime based upon downloaded startTime
                        sqlstr = 'updateTime = "' + record['timestamp'] + '" WHERE startTime = "' + convertDateToStr(eventStartTime) + '"'
                        sql = 'UPDATE lastEvent SET ' + sqlstr
                        c.execute(sql)

                # Committing changes...
                conn.commit()
                #   End DB insert...
                rainDataCounter = record['Rain Counter']
                record = {}
                data = {}

        else:
            False
            sys.stdout.write( nowStr() + ' - stderr: ' + line)
            if (( line.find( 'Failed') != -1) or ( line.find( 'No supported devices') != -1)):
                sys.stdout.write( '   >>>---> ERROR, exiting...\n\n')
                exit( 1)

    sys.stdout.flush()
