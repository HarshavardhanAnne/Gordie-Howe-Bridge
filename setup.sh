#!/bin/bash

###BEGIN####

#Update and upgrade packages
sudo apt-get update
sudo apt-get upgrade

#Usb automount installation
sudo apt-get install usbmount

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

#Modify crontab
(sudo crontab -l ; echo "@reboot /usr/bin/python /home/pi/sph-batt/main.py &") | sudo crontab -

#Overwrite existing hwclock-set file with modified hwclock-set file
sudo chmod +x hwclock-set
sudo /bin/cp -rf hwclock-set /lib/udev/

#Modify /boot/config.txt and add dtoverlay and enable i2c_arm
sudo echo "dtoverlay=i2c-rtc,ds3231" >> /boot/config.txt
sudo echo "dtparam=i2c_arm=on" >> /boot/config.txt


#Adafruit_MCP3008 installation
sudo apt-get update
sudo apt-get install build-essential python-dev python-smbus python-pip
sudo pip install adafruit-mcp3008

#Pull all submodule repo's files
sudo git submodule init
sudo git submodule update

#Install the am2315 python library
sudo apt-get install i2c-tools
sudo apt-get install python-dev
sudo apt-get install libi2c-dev
sudo python ./lib/am2315/setup.py install

###END####
