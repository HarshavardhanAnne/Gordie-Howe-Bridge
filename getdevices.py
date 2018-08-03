import sys
import glob
import serial
import os

def serial_ports(path=None):
	#ports = glob.glob('/dev/ttyUSB[0-15]*')
	if path is None:
		path = '/dev/*'
	ports = glob.glob(path)
	result = []

	for port in ports:
		result.insert(0,port)
	return result

def get_sym_link(input_link):
	return os.readlink(input_link)
'''
res = serial_ports()

p = '/dev/aethlabs'

if p in serial_ports():
	print "Its in there"
	slink = os.readlink(p)
	print slink
else:
	print "nah you good"
'''
