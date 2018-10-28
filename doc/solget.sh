#!/bin/bash
#
####################################################################
# Written by Marcel Reinieren, marcel@reinieren.net        	       #
# Last modified on July 23, 2013                                   #
# Script written for Soladin600                                    #
# Version 2.42                                                     #
####################################################################
#This program is free software and is available under the terms of #
#the GNU General Public License. You can redistribute it and/or    #
#modify it under the terms of the GNU General Public License as    #
#published by the Free Software Foundation.                        #
#                                                                  #
#This program is distributed in the hope that it will be useful,   #
#but WITHOUT ANY WARRANTY; without even the implied warranty of    #
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the     #
#GNU General Public License for more details.                      #
####################################################################
#
##User defined Variables Section

#Comport where Soladin converter is connected
PORT=/dev/tts/1

#Communication will retried if a measurement fails (bad data, or at night)
#Fail variable control how many times the script will try to get data before exiting.
redo=3

#Location of communication logfile
LOG=/var/log/soladin.log

#Location to write the html output
HTML=/share/www/actual.html
#Static background image for HTML (must be placed in same html output location)
BGIMG=solar.jpg

#Location to write comma delimited file with daily Solar results
CSV=/var/log/profit.csv

#Directory to place temporary files (without ending /)
WORKDIR=/tmp

#If RRD is not installed or not wanted change value into 0 (zero)
USE_RRD=1
#RRD database location (without ending /)
RRDDIR=/var/lib/rrd

#RRD Graphs location (www location for use on a website) (without ending /)
GRAPHDIR=/share/www/

#Offset to be used for inverter replacement
#By setting an offset, the HTML output field "Total Amount" will be corrected
#Multiply with 100; If offset must be 12,45 kWh, use value 1245
#Negative values are allowed (refurbished inverter)
WtotOffset=0

#Optional Twitter parameters
#Tweet daily output (Set 1 to tweet)
USE_TWITTER=0
username="YOURTWITTERUSERNAME"
password="YOURTWITTERPASSWORD"

#Optional PVOutput parameters
USE_PVOUTPUT=0
PVOUTPUT_APIKEY="YOUR_PVOUTPUT_APIKEY"
SYSTEM_ID="YOURPVOUTPUT_SYSTEMID"
CURL_OPT=$WORKDIR/PVOUT_EX
PVoutputlog=/var/log/pvoutput.log

#End of user defined Variables Section####################

#Internal program variables 

#Working output file for html creation
TMP=$WORKDIR/index.new

#Working output file for data from soladin
OUT=$WORKDIR/output

#File to store values needed for daily measurements
STORE=$WORKDIR/solar.tmp

#Soladin's command for receiving data
CMD="\x11\x00\x00\x00\xB6\x00\x00\x00\xC7"

#RRD database names
RRDSOL=$RRDDIR/solar_power.rrd

#End of variables section#################################

#Program Routines

#Help
help(){
echo ""
echo "This script is written for Soladin 600."
echo "It will get soladin actual values and store them into readable files (and RRD)"
echo "First open this script to change all user variables into proper values."
echo "afterwards, run \"solget.sh create\" to create initial files."
echo ""
echo "Normal usage is done with \"solget.sh\" without options."
echo "Use cron to run it continuously."
echo "This script is designed for 5 minutes interval runtimes."
echo "a logfile will be created for error logging, and start-stop times"
echo ""
echo "Graphs will be created in png format automatically each hour, and with \"solget.sh draw\"."
echo ""
echo "Written by Marcel Reinieren (c) 2013"
echo "marcel@reinieren.net"
echo ""
}

#create output files and rrd databases
create()
{
#create empty bucket
echo 0 0 0 0 0 > $STORE

#create csv
echo "Date;Profit;Duration" > $CSV

#Create RRD Databases
if (( USE_RRD )); then
   	mkdir -p $RRDDIR
	
  rrdtool create $RRDSOL -s 300 \
	  DS:pwr5:GAUGE:600:0:500 \
	  RRA:AVERAGE:0.5:1:576 \
	  RRA:AVERAGE:0.5:6:672 \
	  RRA:AVERAGE:0.5:12:87600 \
	  RRA:MAX:0.5:6:672 \
    RRA:MAX:0.5:24:43800
	  
fi
}

# Ask data from Soladin
get_data () {
printf $CMD > $PORT
dd if=$PORT of=$OUT bs=1 count=31 &
PID=$!
sleep 3
if [ -d /proc/$PID ]
then
  rcvd="no"
  kill $PID
else
  rcvd="yes"
fi
}

#Put received data in array and check for errors
chk_data () {
data=(`od -b -v $OUT | sed -e 's/^[0-9]*//g' | sed -e 's/[ ]\([0-9]\)/ 0\1/g'`)
 if [ ${#data[@]} -ne 31 ]; then
   rcvd="nochk"
   echo -e `date -R`":  Wrong amount of data received\r" >> $LOG
 else
   sumstr="${data[@]:0:30}"
   let sum=${sumstr// /+}
   if ((sum%256 == data[30])); then
      rcvd="chk"
   else
      rcvd="nochk"
      echo -e `date -R`":   Checksum error in received data\r" >> $LOG
   fi
 fi
}

#convert data from array into readable data
conv_data () {
#errorbits 
(( errbits = data[7] * 256 + data[6] ))
#Voltage Solarpanels (Usol)
(( Usol = data[9] * 256 + data[8] ))
#Power Solarpanels (Isol)
(( Isol = data[11] * 256 + data[10] ))
#Netfrequency (Fnet)
(( Fnet = data[13] * 256 + data[12] ))
#Netvoltage (Unet)
(( Unet = data[15] * 256 + data[14] ))
#Actual output Soladin (Wsol)
(( Wsol = data[19] * 256 + data[18] ))
#Total delivered (Wtot)
(( Wtot = data[22] * 65536 + data[21] * 256 + data[20] ))
#Temp Soladin (Tsol)
(( Tsol = data[23] ))
#Total runtime (Htot)
(( Htot = data[26] * 65536 + data[25] * 256 + data[24] ))
}

#check, convert and write error messages
chk_msg() {
ErrorStr=""
if (( errbits )); then
    if (( errbits & 0x01 )); then
      ErrorStr="Usolar too high (`print_float 1 $Usol` V). ${ErrorStr}"
    fi
    if (( errbits & 0x02 )); then
      ErrorStr="Usolar too low (`print_float 1 $Usol` V). ${ErrorStr}"
    fi
    if (( errbits & 0x04 )); then
     ErrorStr="No mains detected. ${ErrorStr}"
    fi
    if (( errbits & 0x08 )); then
     ErrorStr="Uac too high (${Unet} V).  ${ErrorStr}"
    fi
    if (( errbits & 0x10 )); then
      ErrorStr="Uac too low (${Unet} V). ${ErrorStr}"
    fi
    if (( errbits & 0x20 )); then
      ErrorStr="FreqAC too high (`print_float 2 $Fnet` Hz). ${ErrorStr}"
    fi
    if (( errbits & 0x40 )); then
      ErrorStr="FreqAC too low (`print_float 2 $Fnet` Hz). ${ErrorStr}"
    fi
    if (( errbits & 0x80 )); then
      ErrorStr="Temperature error (${Tsol}ºC). ${ErrorStr}"
    fi
    if (( errbits & 0x100 )); then
      ErrorStr="Hardware error. ${ErrorStr}"
    fi
    if (( errbits & 0x200 )); then
      ErrorStr="Starting. ${ErrorStr}"
    fi
    if (( errbits & 0x400 )); then
      ErrorStr="Max output (${Wsol} W). ${ErrorStr}"
    fi
    if (( errbits & 0x800 )); then
      ErrorStr="I max (`print_float 2 $Isol` A). ${ErrorStr}"
    fi
    echo -e `date -R`":   Error message: $ErrorStr\r" >> $LOG
fi
}

#create floating point values
print_float () {
   let decval=$2
   let l=${#decval}-$1
   if ((l > 0 )); then
      echo ${decval:0:$l},${decval:$l:$1}
   else
      printf "0,%0*u\n" $1 $decval
   fi
}

#create time output
print_time () {
   (( H = $2 /60 ))
   (( M = $2 - 60*H ))
case "$1" in
  "1" ) echo $H" Uur, "$M" Minuten";;
  "2" ) echo $H":"$M;;
esac
}

# create HTML page with actual data.
format_page () {
(( Wtoday = Wtot - store[3] ))
(( Htoday = Htot - store[4] ))
(( WtotAll = Wtot + WtotOffset ))
if (( Wsol )) ; then 
  (( Perf = Wsol * 1000000 / Usol / Isol ))
else
  Perf=0
fi
(( CO2 = Wtoday * 47 / 100 ))
(( CO2tot = WtotAll * 47 / 100 ))
echo "<html><head><title>Solar output</title></head>" > $TMP
echo "<body BGCOLOR=\"000066\" TEXT=\"#E8EEFD\" LINK=\"#FFFFFF\" VLINK=\"#C6FDF4\" ALINK=\"#0BBFFF\" BACKGROUND=\"$BGIMG\">" >> $TMP
echo "<TABLE BORDER=1 CELLPADDING=1 CELLSPACING=2 BGCOLOR=\"#1A689D\" BORDERCOLOR=\"#0DD3EA\" ALIGN=\"CENTER\">" >> $TMP
echo "<TR><TD><font size=5>Live Soladin measurements</font></TD><TR>" >> $TMP
echo "<TR><TD>"`print_float 1 $Usol`" V</TD><TD>Solar Voltage</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $Isol`" A</TD><TD>Solar Current</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $Fnet`" Hz</TD><TD>Net Frequency</TD></TR>" >> $TMP
echo "<TR><TD>"$Unet" V</TD><TD>Net Voltage</TD></TR>" >> $TMP
echo "<TR><TD>"$Wsol" W</TD><TD>Inverter Output Power</TD></TR>" >> $TMP
echo "<TR><TD>"$Tsol"&deg;C</TD><TD>Inverter Temperature</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 1 $Perf`" %</TD><TD>Yield</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $Wtoday`" kWh</TD><TD>Total delivery (today)</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $CO2`" kg</TD><TD>CO&#8322; reduction (today)</TD></TR>" >> $TMP
echo "<TR><TD>"`print_time 1 $Htoday`"</TD><TD>Runtime today</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $WtotAll`" kWh</TD><TD>Total delivery</TD></TR>" >> $TMP
echo "<TR><TD>"`print_float 2 $CO2tot`" kg</TD><TD>Total CO&#8322; reduction</TD></TR>" >> $TMP
echo "<TR><TD>"`print_time 1 $Htot`"</TD><TD>Total runtime</TD></TR>" >> $TMP
echo "<TR><TD><FONT COLOR=red>"$ErrorStr"</FONT></TD><TD>Errors</TD></TR>" >> $TMP
echo "<TR><TD>"`date -R`"</TD><TD>Date/Time</TD></TR></table>" >> $TMP
echo "<BR><BR><center><font size=5>Written by Marcel Reinieren - 2013</center></font></body></html>" >> $TMP
mv $TMP $HTML
}

#Update RRD Databases
rrd_update(){
if (( USE_RRD )) ; then
   rrdtool update $RRDSOL N:${Wsol}
fi
}

#Variables collection for RRD graph
graph()
{
	RRDB=$RRDDIR/solar_power.rrd
		NOW=`date +%s`
		ONE_DAY_AGO=$(($NOW-86400))
		ONE_WEEK_AGO=$(($NOW-604800))
		ONE_MONTH_AGO=$(($NOW-2419200))
		ONE_YEAR_AGO=$(($NOW-29030400))
		TIMESTAMP="Generated on `date|sed 's/:/\\\\:/g'`"
		draw_graphic 'solar_power_last_day.png' $ONE_DAY_AGO $NOW "last 24 hours" "$TIMESTAMP"
		draw_graphic 'solar_power_last_week.png' $ONE_WEEK_AGO $NOW "last week" "$TIMESTAMP"
		draw_graphic 'solar_power_last_month.png' $ONE_MONTH_AGO $NOW "last month" "$TIMESTAMP"
		draw_graphic 'solar_power_last_year.png' $ONE_YEAR_AGO $NOW "last year" "$TIMESTAMP"
}

#Call RRD graph for generating graphs
draw_graphic()
{
	rrdtool graph $GRAPHDIR/$1 -s $2 -e $3 -a PNG \
		-t "Solar output $4" \
		-l 0 -r --units-exponent 0 \
		-v "Watt" \
		DEF:pwr5=$RRDB:pwr5:AVERAGE LINE1:pwr5#ff8080:"Solar power output" \
		COMMENT:"\n" \
		COMMENT:"$5\n"
}

#CSV filler routine
fill_csv() {
(( Wtoday = store[1] - store[3] ))
(( Htoday = store[2] - store[4] ))
if (( ! Htoday )); then
  echo -e `date -R`":   Soladin not started today\r" >> $LOG
  else
  (( store[3] = store[1] ))
  (( store[4] = store[2] ))
fi
echo -e `date +%d-%m-%y`";"`print_float 2 $Wtoday`";"`print_time 2 $Htoday`"\r" >> $CSV
}

#Twitter routine
 twitter(){
 tweet="Today's Solar energy output: "`print_float 2 $Wtoday`" kWh -  "`print_float 2 $CO2`" kg CO2 reduction ~ #SolGet Soladin monitoring http://www.solget.nl"
 uagent="Mozilla/5.0" #user agent (fake a browser)
 cookie=$WORKDIR/cookie.txt
 if [ $(echo "${tweet}" | wc -c) -gt 140 ]; then
       echo -e `date -R`":   [Twitter error] Tweet is over 140 chars.\r" >> $LOG
 fi
 
touch $cookie #create a temp. cookie file
 
#INITIAL PAGE
initpage=`curl -s -b $cookie -c $cookie -L --sslv3 -A "$uagent" "https://mobile.twitter.com/session/new"`
token=`echo "$initpage" | grep "authenticity_token" | sed -e 's/.*value="//' | sed -e 's/" \/>.*//'`
 
#LOGIN
loginpage=`curl -s -b $cookie -c $cookie -L --sslv3 -A "$uagent" -d "authenticity_token=$token&username=$username&password=$password" "https://mobile.twitter.com/session"`
 
#HOME PAGE
homepage=`curl -s -b $cookie -c $cookie -L -A "$uagent" "http://mobile.twitter.com/"`
 
#TWEET
tweettoken=`echo "$homepage" | grep "authenticity_token" | sed -e 's/.*value="//' | sed -e 's/" \/>.*//' | tail -n 1`
update=`curl -s -b $cookie -c $cookie -L --sslv3 -A "$uagent" -d "authenticity_token=$tweettoken&tweet[text]=$tweet&tweet[display_coordinates]=false" "https://mobile.twitter.com/"`
 
#LOGOUT
logout=`curl -s -b $cookie -c $cookie -L --sslv3 -A "$uagent" "https://mobile.twitter.com/session/destroy"`
rm $cookie
}
pvoutput(){
echo "-d \"d=`date +"%Y%m%d"`\"" > $CURL_OPT
echo "-d \"t=`date +"%H:%M"`\"" >> $CURL_OPT
echo "-d \"v1=$((Wtoday*10))\"" >> $CURL_OPT
echo "-d \"v2=$Wsol\"" >> $CURL_OPT
echo "-d \"v6=`print_float 1 $Usol | sed 's/\,/./'`\"" >> $CURL_OPT
echo "--header \"X-Pvoutput-Apikey: $PVOUTPUT_APIKEY\" " >> $CURL_OPT
echo "--header \"X-Pvoutput-SystemId: $SYSTEM_ID\" " >> $CURL_OPT
echo "--url http://pvoutput.org/service/r2/addstatus.jsp" >> $CURL_OPT
pvupdstatus=`curl -q -K $CURL_OPT`

if [[ $pvupdstatus != "OK 200: Added Status" ]]; then
        echo -e `date -R`":   PVoutput upload failed!" >>$LOG
        cp $CURL_OPT $CURL_OPT-`date +"%Y-%m-%d-%H%M%S"`
        echo -e `date -R`": "$pvupdstatus >> $PVoutputlog
fi
}

# Main Program
main(){
#set time variables
MTIME=`date +%M`
HTIME=`date +%H`

# Configure serial port
stty -hupcl -clocal ignbrk -icrnl -ixon -opost -onlcr -isig -icanon -iexten -echo -echoe -echok -echoctl -echoke 9600 -crtscts <$PORT

#Store file contains data needed for calculating totals etc
#Internally an array is used, values are:
#0=Active flag
#1=WtotAct
#2=HtotAct
#3=WtotLog
#4=HtotLog
#fill array
store=(`cat $STORE`)

#Run all routines in correct order
while (( redo )) ; do
	get_data < $PORT 2>/dev/null
	if [ $rcvd = "yes" ]; then
          if (( ! store[0] )) ; then
            echo -e `date -R`":   Waking up; Soladin started.\r" >> $LOG
            store[0]=1
          fi
          chk_data
          if [ $rcvd = "chk" ]; then
	         conv_data
	         chk_msg
	         # Put total values into array for calculating daily profit
	         store[1]=$Wtot
	         store[2]=$Htot
	         format_page
		     if (( USE_PVOUTPUT )); then
                 pvoutput
             fi
             rrd_update
             redo=0
          else
            ((redo -= 1))
	      fi
	else
      ((redo -= 1))
	fi
done

#Write message before sleep
if [ $rcvd = "no" ] && (( ! redo )) && (( store[0] )) ; then
   echo -e `date -R`":   No reaction from soladin; entering sleep\r" >> $LOG
   (( Wtoday = store[1] - store[3] ))
   (( Htoday = store[2] - store[4] ))
   (( WtotAll = store[1] + WtotOffset ))
   (( CO2 = Wtoday * 47 / 100 ))
   (( CO2tot = WtotAll * 47 / 100 )) 
   
   echo "<html><head><title>Solar output</title></head>" > $TMP
   echo "<body BGCOLOR=\"000066\" TEXT=\"#E8EEFD\" LINK=\"#FFFFFF\" VLINK=\"#C6FDF4\" ALINK=\"#0BBFFF\" BACKGROUND=\"$BGIMG\">" >> $TMP
   echo "<TABLE BORDER=1 CELLPADDING=1 CELLSPACING=2 BGCOLOR=\"#1A689D\" BORDERCOLOR=\"#0DD3EA\" ALIGN=\"CENTER\">" >> $TMP
   echo "<TR><TD><font size=4>Soladin offline</font></TD><TR>" >> $TMP
   echo "<TR><TD>"`print_float 2 $Wtoday`" kWh</TD><TD>Total delivery (last day)</TD></TR>" >> $TMP
   echo "<TR><TD>"`print_float 2 $CO2`" kg</TD><TD>CO&#8322; reduction</TD></TR>" >> $TMP
   echo "<TR><TD>"`print_time 1 $Htoday`"</TD><TD>Runtime</TD></TR>" >> $TMP
   echo "<TR><TD>"`print_float 2 $WtotAll`" kWh</TD><TD>Total delivery</TD></TR>" >> $TMP
   echo "<TR><TD>"`print_float 2 $CO2tot`" kg</TD><TD>CO&#8322; reduction</TD></TR>" >> $TMP
   echo "<TR><TD>"`print_time 1 ${store[2]}`"</TD><TD>Total runtime</TD></TR>" >> $TMP
   echo "<TR><TD>"`date -R`"</TD><TD>Date/Time</TD></TR></table>" >> $TMP
   echo "<BR><BR><center><font size=5>Written by Marcel Reinieren - 2013</center></font></body></html>" >> $TMP
   mv $TMP $HTML
   
   store[0]=0
   if (( USE_TWITTER )); then 
   twitter
   fi
fi

#Run timebased scripts (internal cron)
if [ $HTIME = 23 ] && [ $MTIME = 55 ]; then
  fill_csv
fi
if [ $MTIME = 00 ] && (( USE_RRD )); then
  graph
fi

#storing variables to working file
echo ${store[0]} ${store[1]} ${store[2]} ${store[3]} ${store[4]} > $STORE
}


case $1 in
"help" )
help
;;
"create" )
create
;;
"draw" )
graph
;;
* )
main
;;
esac
