SolGet - Logging Script for Soladin 600

Written in Bash *** Marcel Reinieren (c) 2007 - 2013

SolGet will read data from Soladin 600 inverter through serial communication. All internal measurement values will be read. After reading, SolGet will convert these binary values into readable output. This output is used in several outputs.
-HTML output; to show your Solar production on a website
-Logging in CSV file; Daily totals will be written in a file (Also Error messages will be logged)
-Database; An RRD database can be filled to produce graphs
-Twitter; Solget can send a daily tweet with daily production data
-PVoutput: Solget can send your data automatically to PVoutput, if you create an account at pvoutput.org. Please join the Solget group! Find it at http://pvoutput.org/listteam.jsp?tid=607

Solget is free to use. Solget is published under the GNU General Public License.

*********************************************
Solget is developed on an embedded linux device (Asus wl500g router with custom linux (OLEG) firmware). Busybox 1.1.3 is used for al external commands. Problems on other linux distributions are not expected.
An interface cable is required to connect your Soladin to the computer where Solget will reside. This can be an official PC-Link (Mastervolt product), Sol-Link or self-made cable. It is serial communication. To connect the soladin on an USB port, it is possible to use a converter. (usb2serial)

The script is based on periodical measurements. (Each 5 minutes) Cron is used for this.

Solget is using several external programs.

A webserver (apache, thttpd, busybox_httpd, etc) for showing HTML output in a browser
RRDtool (For the RRD database and creating graphs)

Of course you will need cron, and nano/vi for editing.

NB: Installing additional software, connecting a serial port on a router, etc is not part of this readme. 

Solget detects if the soladin is running. If the soladin does not respond, Solget assumes it is offline, this will be written in de logfile and HTML output.
Housekeeping tasks will run at 11:55PM. (NB: In rare situations when soladin is still running at midnight (eg north scandinavia region during summer), this will cause some miscalculations)

RRDTool is optional, Solget can run without storing data in the database and creating graphs.


*********************************************
Preparation

First, change all variables to correct values.

PORT: Choose the correct comport. (eg: /dev/ttyS0)

redo: Solget will do retries if the communication fails. In some situations (lots of interference, bad/very long cable) it can be neccessary to increase the default value. (Default=3 which is recommended)

LOG: Logfile for communication errorlogging. (Full Path)

CSV: CSV File to write daily production data. (Full Path)

WORKDIR: Temporary files location (Full path without slash at the end)

USE_RRD: Self explaining; 0 to disable RRDtool, 1 to enable RRDTOOL usage.

RRDDIR: Location for RRDTOOL database file. (Full path without slash at the end)

GRAPHDIR: Location for storing graph files (.PNG type). (Full path without slash at the end)

WtotOffset: This value can be used to set an offset for total production value. (eg. if the soladin is replaced) Both positive and negative offset values are accepted. Multiply the desired value by 100. (eg. An offset of 1245,36kWh must be set to 124536.) NB: This value will not affect values written in CSV.

USE_TWITTER: Default value=0. To enable daily tweets, set this to 1.
username: Twitter username
password: TWitter password

USE_PVOUTPUT=0 Default value=0. To enable PVoutput.org uploads, set this to 1.
PVOUTPUT_APIKEY="YOUR_PVOUTPUT_API_KEY"
SYSTEM_ID="PVOUTPUT_SYSTEMID"
CURL_OPT=$WORKDIR/PVOUT_EX (file to gather values before uploading.)
PVoutputlog=/opt/tmp/PVoutput.log (Logfile to store upload messages)

Solget will not create directories, so create them with mkdir if they don't exist. (Files will be created if needed)

Check the interpreter value (first line of the script). Many embedded linux systems have bash installed under /opt.
On other distributions (like ubuntu) bash is installed in /bin so change the value to #!/bin/bash. 


After setting the variables, initial files must be created by running:  solget.sh create

This command will not produce any output if initialising is successfull.

Preparation is complete now.

*********************************************
Running the script

Create a new line in your cron configuration (eg /opt/etc/crontab) 

*/5 * * * * root /opt/usr/bin/solget.sh

Root is your local admin account. Of course change the path if solget is installed in another directory.

It's allowed to run solget more than once per 5 minutes. It is not needed to wait 5 minutes during troubleshooting. (RRDTool will handle additional values automatically.)

The Errorlog will be written after the first message/error occurs. 

In case an error occurs during PVoutput.org uploads, the values will be stored in a file with date/time according to the chosen value in CURL_OPT. These records can be uploaded later after the connection to pvoutput.org is re-established. use the command "curl -q -K FILENAME" for this. Needless to say, your APIKEY and SYSTEMID must be correct beforehand. Be aware of a limited uploads, PVOUTput will limit the amount of uploads per APIKEY. 

*********************************************
SUPPORT:

For Questions, remarks, problems, post on the forums, facebook (www.facebook.com/Solget.nl), mail (mail@solget.nl), or use the mailform on my website. (www.solget.nl)

Thanks for using SolGet!

If you want to thank me, consider a donation using the PayPal donate button on my website. (www.solget.nl)
