#!/usr/bin/env python

from datetime import datetime, timedelta
import urllib, xmltodict
import re, math, time, sqlite3
#####################################################################
#   ******** UPDATE These to match your configuration ************  #
#####################################################################
WLTagsPath = '/var/www/html/weather/WLtags.php' #path to WLTags.php in Saratoga Weather web files
WLTagsHTXPath = '/var/www/html/weather/WXtags-template-files/WLtags.htx' # path to the htx template
# http://www.aviationweather.gov and choose 4 letter ID for an airport near you
baroStation = 'KGON'

conn  = sqlite3.connect("/path/to/acurite.sqlite")

##########################################################################

cursor = conn.cursor()

def convertToDateTime(dateString):
    print 'converting to datetime %s ' % dateString
    return( datetime.strptime( dateString, '%Y-%m-%d %H:%M:%S'))

def getBaro ():
    baroUrl = "http://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString=" + baroStation + "&hoursBeforeNow=1&mostRecent=true"
    response = urllib.urlopen(baroUrl)
    metar = xmltodict.parse(response)['response']['data']['METAR']
    #print metar
    return metar['altim_in_hg']

def getHourOldBaro():
    oldBaroUrl = "http://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString=" + baroStation +"&hoursBeforeNow=1"
    response = urllib.urlopen(oldBaroUrl)
    metar = xmltodict.parse(response)['response']['data']['METAR']
    index = len(metar) -1
    print metar[index]['altim_in_hg']
    return metar[index]['altim_in_hg']


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

def calcStormRain(beginTime):
        #startTime = convertToDateTime(beginTime)
        #startTime = beginTime
        sql = 'SELECT min(rainCounter), max(rainCounter) FROM wxInfo WHERE insDate > \''  + beginTime + '\''
        cursor.execute(sql)
        rainData = cursor.fetchone()
        minCounter = rainData[0]
        maxCounter = rainData[1]
        counter = maxCounter - minCounter
        return counter + 1  #need to add 1 because you start with the new value, not the last counter

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
# maps the  Compass Rose Direction to Wind Direction
windDirectionLookup = {
    'NW' : '315.0',
    'WSW': '247.5',
    'WNW': '292.5',
    'W'  : '270.0',
    'NNW': '337.5',
    'SW' : '225.0',
    'N'  : '0.0',
    'SSW': '202.5',
    'ENE': '67.5',
    'SE' : '135.0',
    'E'  : '90.0',
    'ESE': '112.5',
    'NE' : '45.0',
    'SSE': '157.5',
    'NNE': '22.5',
    'S'  : '180.0'
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

# Define timeframe
startOfLastMonth = 'datetime(\'now\', \'localtime\', \'-1 months\',\'start of month\')'
startOfThisMonth = 'datetime(\'now\', \'localtime\', \'start of month\')'
startOfYesterday =  'datetime(\'now\', \'localtime\', \'-1 days\',\'start of day\')'
endOfYesterday = 'datetime(\'now\', \'localtime\',\'start of day\', \'-0.1 seconds\')'

# Grab Max wind and Rain information for the month
sql = 'SELECT max(windSpeed), min(rainCounter), max(rainCounter) FROM wxInfo WHERE insDate BETWEEN ' + startOfThisMonth + 'AND datetime(\'now\', \'localtime\')'
cursor.execute(sql)
monthData = cursor.fetchone()
maxWindMonth = str(int(monthData[0]))
minRainCounterMonth = monthData[1]
maxRainCounterMonth = monthData[2]

#Today's max/min temp and max windSpeed
sql = 'SELECT min(temp), max(temp), max(windSpeed) FROM wxInfo WHERE insDate BETWEEN datetime(\'now\', \'localtime\',\'start of day\') AND datetime(\'now\', \'localtime\')'
cursor.execute(sql)
tempData = cursor.fetchone()
minTemp = str(tempData[0])
maxTemp = str(tempData[1])
dailyMaxWindspeed = str(tempData[2])

#Grab gust (max windspeed over 10 minutes)
sql = 'SELECT max(Windspeed) FROM wxInfo WHERE insDate > datetime(\'now\', \'localtime\',\'-10 minutes\')'
cursor.execute(sql)
gustData = cursor.fetchone()
windGust = str(gustData[0])

#daily Max Windspeed time
sql = 'SELECT insDate FROM wxInfo WHERE insDate BETWEEN datetime(\'now\', \'localtime\',\'start of day\') AND datetime(\'now\', \'localtime\') AND windSpeed = ' + dailyMaxWindspeed + ' ORDER BY insDate ASC LIMIT 1'
cursor.execute(sql)
dailyMaxWindspeedData = cursor.fetchone()
dailyMaxWindspeedTime = convertToDateTime(dailyMaxWindspeedData[0])
dailyMaxWindspeedTimeStr = dailyMaxWindspeedTime.strftime('%H:%M')

#Todays' minTemp Time
sql = 'SELECT insDate FROM wxInfo WHERE insDate BETWEEN datetime(\'now\', \'localtime\',\'start of day\') AND datetime(\'now\', \'localtime\') AND temp = ' + minTemp + ' ORDER BY insDate ASC LIMIT 1'
cursor.execute(sql)
minTempTimeData = cursor.fetchone()
minTempTime = convertToDateTime(minTempTimeData[0])
minTempTimeStr = minTempTime.strftime('%H:%M')

#Todays' maxTemp Time
sql = 'SELECT insDate FROM wxInfo WHERE insDate BETWEEN datetime(\'now\', \'localtime\',\'start of day\') AND datetime(\'now\', \'localtime\') AND temp = ' + maxTemp + ' ORDER BY insDate ASC LIMIT 1'
cursor.execute(sql)
maxTempTimeData = cursor.fetchone()
maxTempTime = convertToDateTime(maxTempTimeData[0])
maxTempTimeStr = maxTempTime.strftime('%H:%M')

#Yesterday's max/minTemp
sql = 'SELECT min(temp), max(temp) FROM wxInfo WHERE insDate BETWEEN datetime(\'now\',\'localtime\',\'start of day\', \'-1 days\') AND datetime(\'now\',\'localtime\', \'start of day\')'
cursor.execute(sql)
tempData = cursor.fetchone()
yminTemp = str(tempData[0])
ymaxTemp = str(tempData[1])

#Yesterdays's minTemp Time
sql = 'SELECT insDate FROM wxInfo WHERE insDate BETWEEN datetime(\'now\',\'localtime\',\'start of day\', \'-1 days\') AND datetime(\'now\',\'localtime\', \'start of day\')  AND temp = ' + yminTemp + ' ORDER BY insDate ASC LIMIT 1'
cursor.execute(sql)
yminTempTimeData = cursor.fetchone()
yminTempTime = convertToDateTime(yminTempTimeData[0])
yminTempTimeStr = yminTempTime.strftime('%H:%M')

#Yesterday's maxTemp Time
sql = 'SELECT insDate FROM wxInfo WHERE insDate BETWEEN datetime(\'now\',\'localtime\',\'start of day\', \'-1 days\') AND datetime(\'now\',\'localtime\', \'start of day\')  AND temp = ' + ymaxTemp + ' ORDER BY insDate ASC LIMIT 1'
cursor.execute(sql)
ymaxTempTimeData = cursor.fetchone()
ymaxTempTime = convertToDateTime(ymaxTempTimeData[0])
ymaxTempTimeStr = ymaxTempTime.strftime('%H:%M')

#Calculate Dew Point  Temp - 9/25 * (100 - RH)
sql = 'SELECT temp, humidity, insDate FROM wxInfo ORDER BY insDate DESC LIMIT 1'
cursor.execute(sql)
data = cursor.fetchone()
temp = float(data[0])
humidity = float(data[1])
dewPoint = temp - ((100 - humidity) * float(9)/25)
readTime = convertToDateTime(data[2])
readTimeStr = readTime.strftime('%H:%M')
readDateStr = readTime.strftime('%x')

#grab hour old Temp for trends
sql = 'SELECT avg(temp), avg(humidity) FROM wxInfo  WHERE insDate >= datetime(\'now\', \'localtime\', \'-1 hours\')'
cursor.execute( sql)
oneHourdata = cursor.fetchone()
oneHourTemp = oneHourdata[0]
avghumidity = oneHourdata[1]
print oneHourTemp
print ('tempdif: {0}'.format(round(temp - oneHourTemp)))
lastDew = oneHourTemp - ((100 - avghumidity) * float(9)/25)
#Calculate Avg Wind
sqlStmt = 'SELECT windDirection FROM wxInfo  WHERE insDate >= datetime(\'now\', \'localtime\', \'-5 minutes\')'
cursor.execute( sqlStmt)
winddata = cursor.fetchall()
AverageWindDirection = CalcAvgWind (winddata)
AverageWindDir = windDirectionLookup[AverageWindDirection]

sqlStmt = 'SELECT avg(windSpeed) FROM wxInfo  WHERE insDate >= datetime(\'now\', \'localtime\', \'-5 minutes\')'
cursor.execute( sqlStmt)
fiveMinuteData = cursor.fetchone()
averageWindSpeed = int(round(fiveMinuteData[0]))


#Calculate Daily rain
sql = 'SELECT min(rainCounter), max(rainCounter) FROM wxInfo WHERE insDate BETWEEN datetime(\'now\', \'localtime\',\'start of day\') AND datetime(\'now\', \'localtime\')'
cursor.execute(sql)
rainData = cursor.fetchone()
minCounter = rainData[0]
maxCounter = rainData[1]
counter = maxCounter - minCounter
dailyRain = str(counter * 0.01)

#Calculate Storm Total
sql = 'SELECT startTime FROM lastEvent'
cursor.execute(sql)
rainStart = cursor.fetchone()
rainStartTime = rainStart[0]
#print ('Rain Start Time: {0}'.format(rainStartTime))
if ((datetime.now() - convertToDateTime(rainStartTime)).days < 360):
    rainTotal = calcStormRain(rainStartTime)
    stormRain = str(rainTotal * 0.01)
    print ('Storm Rain is: {0}'.format(stormRain))
else:
    stormRain = '0.0'

#grab seasonal rain Total
sql = 'SELECT sum(eventRainAmount) FROM rainEventData'
cursor.execute(sql)
seasonalRainData = cursor.fetchone()
seasonalRain = seasonalRainData[0]

#Calculate trends
baro = round(float(getBaro()) * 100)/ 100
lastBaro = round(float(getHourOldBaro()) * 100)/ 100
trend = baro - lastBaro
dewchangelasthour = dewPoint - lastDew

#Write the fields to WLtags.htx
filedata = None
with open(WLTagsHTXPath, 'r') as file :
  filedata = file.read()

# Replace the target string
filedata = re.sub('<!--outsideTemp-->', str(temp), filedata)
filedata = re.sub('<!--hiOutsideTemp-->', maxTemp, filedata)
filedata = re.sub('<!--lowOutsideTemp-->', minTemp, filedata)
filedata = re.sub('<!--lowOutsideTempTime-->', minTempTimeStr, filedata)
filedata = re.sub('<!--hiOutsideTempTime-->', maxTempTimeStr, filedata)
filedata = re.sub('<!--maxtempyest-->', ymaxTemp, filedata)
filedata = re.sub('<!--maxtempyestt-->', ymaxTempTimeStr, filedata)
filedata = re.sub('<!--mintempyest-->',yminTemp, filedata)
filedata = re.sub('<!--mintempyestt-->', yminTempTimeStr, filedata)
filedata = re.sub('<!--outsideHumidity-->', str(humidity), filedata)
filedata = re.sub('<!--outsideDewPt-->', str(round(dewPoint)), filedata)
filedata = re.sub('<!--barometer-->', str(baro), filedata)
filedata = re.sub('<!--trend-->', str(trend), filedata)
filedata = re.sub('<!--windDir-->', str(AverageWindDir), filedata)
filedata = re.sub('<!--windDirection-->',str(AverageWindDirection), filedata)
filedata = re.sub('<!--windSpeed-->',str(averageWindSpeed), filedata)
filedata = re.sub('<!--windHigh5-->',windGust, filedata)
filedata = re.sub('<!--hiWindSpeed-->',dailyMaxWindspeed, filedata)
filedata = re.sub('<!--hiWindSpeedTime-->',dailyMaxWindspeedTimeStr, filedata)
filedata = re.sub('<!--hiMonthlyWindSpeed-->',maxWindMonth, filedata)
filedata = re.sub('<!--dailyRain-->',dailyRain, filedata)
filedata = re.sub('<!--stormRain-->',stormRain, filedata)
filedata = re.sub('<!--totalRain-->',str(seasonalRain), filedata)
filedata = re.sub('<!--monthlyRain-->',str((maxRainCounterMonth - minRainCounterMonth) * 0.01), filedata)
filedata = re.sub('<!--date-->',readDateStr, filedata)
filedata = re.sub('<!--time-->',readTimeStr, filedata)
filedata = re.sub('<!--tempchangehour-->', str(round(temp - oneHourTemp)), filedata)
filedata = re.sub('<!--dewchangelasthour-->', str(dewchangelasthour), filedata)

file.close() # WLTags.htx

# Write the file out to WLtags.php
with open(WLTagsPath, 'w') as file:
  file.write(filedata)
file.close()
