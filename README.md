# RpiVirtualWxStation

There are many variants of virtual weather stations on the web and github. However, many gather information directly from some type of display device through the attached USB.  My weather display device doesn't have a USB.  So I created this configuration to gather my farm's weather and Saratoga templates to display the information.    

Hardware:
Acurite 5n1 (not the pro) 433 mhz
Raspberry Pi 2
NooElec NESDR Mini SDR & DVB-T USB Stick (RTL2832 + R820T) w/ Antenna

Software:
https://github.com/merbanan/rtl_433
http://saratoga-weather.org/wxtemplates/WXwebsite.php
rtl_433_wrapper.py (can't find original source for credit) 
PHP, Python, SQLite3

System:
The system consists of a Raspberry Pi 2 with a DVB-T USB SDR.  Merbanan's rtl_433.92 is called using a wrapper (rtl_433AccuriteToWXSQL.py) which writes Time, Temp, Humidity, Wind Speed, Direction, and Rain Counter to an SQLite3 database.  An intermediate table “lastEvent” is also used to track the storm start time and barometer along with the time when the counter was updated.  Indepentant of this, a cron job runs at a desired interval to check the last time the rain counter was updated.  This cron job determines if it is still raining, or if the storm is over.  If the storm is over, the time when the storm started and the amount of rain is entered into the “rainEventData” table for archive queries (Yearly Rain). From these 3 tables, all my local weather information is tracked for Satatoga-Weather.org templates.  

I used the Base-USA and Weather Link Template sets for the Saratoga virtual weather display. Instead of relying on an expensive Davis weather station to update the weather data, I use Python which reads an SQLite database to create the information Saratoga is looking for.  My scripts create the WLTags.php file which Saratoga parses to create the virtual display.  Really, all of the other magic is handled by Saratoga.  It's up to you how often you would like to update the weather information for the website.  If you're patient and want to keep unnecessary queries from running, then you can modify the wxinfo.php file to run the createWLTags.py script on the fly. Or, you can set up a cron job to constantly update the WLTags file over some interval.  On the fly only delays the page about 1-2 seconds, so I use this method.  

Configuration Highlights:
I assume you have PHP and Apache installed and running.  From here...

1. Install Saratoga Weather PHP templates following the instructions on the site to setup and configure.  I used the Weather Link Template set.  

2. Install Merbanan's rtl_433 

3. Copy  rtl_433AccuriteToWXSQL.py, createWLtages.py, checkStormEvent.py

4. Create the SQLite3 database and tables:

lastEvent: 
   CREATE TABLE IF NOT EXISTS lastEvent (
       startTime               datetime,
       updateTime              datetime,
       startBaro               real
       );

rainEventData:
 CREATE TABLE IF NOT EXISTS rainEventData (
        startTime               datetime,
        eventRainAmount         real
   );

wxInfo: 
CREATE TABLE IF NOT EXISTS wxInfo (
        insDate                 datetime,
        windSpeed               real,
        windDirection           real,
        temp                    real,
        humidity                real,
        rainGauge               real,
        rainCounter             int



5. If you choose to run the weather updates on demand, modify the wxindex.php file by placing an if(){ at the beginning and don't forget the closing } at the end of the file.  The if statement is needed for php to wait until the file is written. I've read a lot of commentary about how this is not necessary, but if I don't do it, the php script grabs the WLTags.php file before the python script can finish writing the file.  Event sleep() statements in the python script didn't' help.  If you have a better way, please let me know!  

	<?php
	$result = exec('/path/to/createWLTags.py');
	if ($result){
		require_once("Settings.php");
		require_once("common.php");
		#############################################################
		$TITLE= $SITE['organ'] . " - Home";
		... 
		... 
		... 
		#####################################################################
		include("footer.php");
	}

6. Create the crontab jobs:
	a. checkStormEvent.py (every 6 mins?)
	b. if you choose to continually update weather creatWLTags.py (every minute?)

7.  I run rtl_433AccuriteToWXSQL.py in a tmux shell to keep it active when I log off.  Other methods exists as you wish. 

TO DO:  
1.  This creates about 2.5Gb files per month.  At a monthly interval, create a script to clean data greater than 2 months out of the database.  

2.  Optimize configuration and queries for speed. Seems like a lot of database calls per weather update.  This is currently exists due to different time requirements per query.  

Please toss me an email if you like this and/or use or have suggestions!
h60pilot@gmail.com
