#!/bin/bash

###BEGIN####

#Update and upgrade packages
echo "Updating and upgrading packages"
sudo apt-get update
sudo apt-get upgrade

#Pull all submodule repo's files
echo "Initializing and pulling all submodule repo files"
sudo git pull
sudo git submodule init
sudo git submodule update --recursive --remote

echo "Installing MCP3008 library"
#Adafruit_MCP3008 installation
sudo apt-get update
sudo apt-get install build-essential python-dev python-smbus python-pip
sudo pip install adafruit-mcp3008

echo "Installing am2315 library and required packages"
#Install the am2315 python library
sudo apt-get install i2c-tools
sudo apt-get install python-dev
sudo apt-get install libi2c-dev
sudo python ./lib/am2315/setup.py install

echo "Installing usbmount"
#Usb automount installation
sudo apt-get install usbmount

echo "Binding /dev/aethlabs to serial cable"
#Bind aethlabs ma200 serial cable to symbolic link
cp ./setup_files/99-usb-serial.rules /etc/udev/rules.d/

#Load the new rule
sudo udevadm trigger

#Check if symbolic link was created
if [ -e /dev/aethlabs ]
then
  echo "Symbolic link created for aethlabs device."
else
  echo "Unable to create symbolic link"
fi

echo "Adding cron job to run main.py on boot"
#Modify crontab
(sudo crontab -l ; echo "@reboot /usr/bin/python /home/pi/Gordie-Howe-Bridge/main.py &") | sudo crontab -

echo "Modifying hwclock file"
#Overwrite existing hwclock-set file with modified hwclock-set file
sudo chmod +x ./setup_files/hwclock-set
sudo /bin/cp -rf ./setup_files/hwclock-set /lib/udev/

echo "Modifying config file for RTC"
#Modify /boot/config.txt and add dtoverlay
sudo echo "dtoverlay=i2c-rtc,ds3231" >> /boot/config.txt

echo "Enabling i2c bus"
#Enable i2c_1 bus
sudo echo "dtparam=i2c_arm=on" >> /boot/config.txt
sudo echo "i2c-dev" >> /etc/modules

echo "Finished"
###END####
