#!/bin/bash

###BEGIN####

#Update and upgrade packages
sudo apt-get update
sudo apt-get upgrade

#Adafruit_MCP3008 installation
sudo apt-get update
sudo apt-get install build-essential python-dev python-smbus python-pip
sudo pip install adafruit-mcp3008

#Install the am2315 python library
cd ./am2315
sudo python setup.py install
cd ../

###END####
