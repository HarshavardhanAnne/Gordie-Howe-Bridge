#!/usr/bin/python
import threading
import time
import sys
import os
from datetime import datetime
sys.path.insert(0, '/home/pi/sph-batt/lib/Met-One-Aerocet-531s-serial/')
sys.path.insert(0, '/home/pi/sph-batt/lib/REED-SD-4023-serial/')
sys.path.insert(0, '/home/pi/sph-batt/lib/AethLabs-MA200-serial/')
from sd_4023 import SD_4023
from aerocet531s import Aerocet531s
from ma200 import MA200
from tentacle_pi.AM2315 import AM2315
import Adafruit_GPIO.SPI as SPI
from Adafruit_MCP3008 import MCP3008
import getdevices
import RPi.GPIO as GPIO

usb_paths = getdevices.serial_ports('/dev/sd*')

if len(usb_paths) == 0:
    local_dir = "/home/pi/sph-batt/data/"
    PATH_TO_USB = os.path.join(local_dir,time.strftime("%Y-%m-%d_%H-%M-%S"))
else:
    usb_dir = "/media/usb/"
    PATH_TO_USB = os.path.join(usb_dir,time.strftime("%Y-%m-%d_%H-%M-%S"))


os.makedirs(PATH_TO_USB)

timestr = PATH_TO_USB + "/debug.log"
sys.stdout = open(timestr,"a",0)

###CONSTANTS####
_DEBUGVAR_ = True
AERO_FILE_NAME = PATH_TO_USB + '/output_aerocet531.log'
SD_FILE_NAME = PATH_TO_USB + '/output_sd4023.log'
CO2_FILE_NAME = PATH_TO_USB + '/output_co2.log'
FLOW_FILE_NAME = PATH_TO_USB + '/output_flow.log'
AM_FILE_NAME = PATH_TO_USB + '/output_am2315.log'
MA200_FILE_NAME = PATH_TO_USB + '/output_ma200.log'
MAX_NUM_RETRIES = 5
CLK = 18
MISO = 23
MOSI = 24
CS = 25
ADC_CO2_PIN = 0
ADC_FLOW_PIN = 2
NUM_MIN_RUN = 525600
STATUS_LED_PIN = 5

OUTPUT_LOG_HEADERS = {'ma200':"Date,Time,Serial number,Datum ID,Session ID,"
                              "Data format version,Firmware version,Date / Time GMT,"
                              "Timezone offset,GPS lat,GPS long,GPS Speed,Timebase,Status,"
                              "Battery,Accel X,Accel Y,Accel Z,Tape position,Flow setpoint,"
                              "Flow total,Sample temp,Sample RH,Sample dewpoint,Int pressure,"
                              "Int temp,Optical config,UV Sen1,UV Ref,UV ATN1,Blue Sen1,"
                              "Blue Ref,Blue ATN1,Green Sen1,Green Ref,Green ATN1,"
                              "Red Sen1,Red Ref,Red ATN1,IR Sen1,IR Ref,IR ATN1,UV BC1,"
                              "Blue BC1,Green BC1,Red BC1,IR BC1,CKSUM\r\n",
                      'sd':'Date,Time,Average(dB),Max(dB)\r\n',
                      'aero':"Date,Time,Record_Date,Record_Time,Time,PM1(ug/m3),PM2.5(ug/m3),"
                             "PM4(ug/m3),PM7(ug/m3),PM10(ug/m3),TSP(ug/m3),AT(F),RH(%),"
                             "Location,Seconds,Status\r\n",
                      'co2':'Date,Time,Analog_Voltage\r\n',
                      'am':'Date,Time,Temp(Celsius),Humidity,crc_check\r\n',
                      'flow':'Date,Time,Analog_Voltage\r\n'}
###ENDCONSTANTS####

###GLOBALS####
SD_SUM = 0
SD_NUM_OF_READS = 0
SD_MAX = 0
STATUS_FLAG_DICT = {'aero':0,'sd':0,'ma200':0}
###ENDGLOBALS####


GPIO.setmode(GPIO.BCM)
GPIO.setup(STATUS_LED_PIN,GPIO.OUT)
GPIO.output(STATUS_LED_PIN,1)


aethlabs_symlink = '/dev/aethlabs'
aethlabs_port = None
aerocet_port = None
sd_port = None
port_list = None

if aethlabs_symlink in getdevices.serial_ports():
    aethlabs_port = '/dev/' + getdevices.get_sym_link(aethlabs_symlink)
else:
    if (_DEBUGVAR_): print ("Unable to find symbolically linked port")

port_list = getdevices.serial_ports('/dev/ttyUSB*')

if (_DEBUGVAR_):
    wap = 0
    print ("Before:")
    for p in port_list:
        print ("%d: %s" % (wap,p))
        wap += 1
if len(port_list) < 3:
    sys.exit(1)

if aethlabs_port is not None and port_list is not None: port_list.remove(aethlabs_port)

if (_DEBUGVAR_):
    print ("After:")
    for p in port_list:
        print (p)

if port_list is not None:
    sd_port = port_list[0]
    aerocet_port = port_list[1]

sdObject = SD_4023(sd_port,1)
aeroObject = Aerocet531s(38400,aerocet_port,1)
maObject = MA200(aethlabs_symlink,1)
mcp = MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)
am = AM2315(0x5c,"/dev/i2c-1")

file_aero = open(AERO_FILE_NAME,"a",0)
file_sd = open(SD_FILE_NAME,"a",0)
file_co2 = open(CO2_FILE_NAME,"a",0)
file_flow = open(FLOW_FILE_NAME,"a",0)
file_am = open(AM_FILE_NAME,'a',0)
file_ma200 = open(MA200_FILE_NAME,"a",0)

if os.path.getsize(AERO_FILE_NAME) == 0:
    print ("(AEROCET531s): Empty output log. Writing header.")
    file_aero.write(OUTPUT_LOG_HEADERS['aero'])
if os.path.getsize(SD_FILE_NAME) == 0:
    print ("(SD4023): Empty output log. Writing header.")
    file_sd.write(OUTPUT_LOG_HEADERS['sd'])
if os.path.getsize(CO2_FILE_NAME) == 0:
    print ("(CO2): Empty output log. Writing header.")
    file_co2.write(OUTPUT_LOG_HEADERS['co2'])
if os.path.getsize(FLOW_FILE_NAME) == 0:
    print ("(FLOW): Empty output log. Writing header.")
    file_flow.write(OUTPUT_LOG_HEADERS['flow'])
if os.path.getsize(AM_FILE_NAME) == 0:
    print ("(AM): Empty output log. Writing header")
    file_am.write(OUTPUT_LOG_HEADERS['am'])
if os.path.getsize(MA200_FILE_NAME) == 0:
    print ("(MA200): Empty output log. Writing header.")
    file_ma200.write(OUTPUT_LOG_HEADERS['ma200'])

def aero_activate_thread():
    if not aeroObject.get_status():
        aeroObject.activate_comm_mode()
    threading.Timer(55.0,aero_activate_thread).start()

def main_thread():
    global SD_SUM
    global SD_MAX
    global SD_NUM_OF_READS
    global STATUS_FLAG_DICT
    global NUM_MIN_RUN

    if NUM_MIN_RUN is None:
        tmain = threading.Timer(60.0,main_thread)
        tmain.setDaemon(True)
        tmain.start()
    elif NUM_MIN_RUN >= 0:
        #NUM_MIN_RUN -= 1
        tmain = threading.Timer(59.0,main_thread)
        tmain.setDaemon(True)
        tmain.start()
    else:
        close_connections()

    STATUS_FLAG_DICT['aero'] = aeroObject.get_status()
    STATUS_FLAG_DICT['sd'] = sdObject.get_status()
    STATUS_FLAG_DICT['ma200'] = maObject.get_status()


    if not STATUS_FLAG_DICT['ma200']:
        ma_data = maObject.read()
        if ma_data is not None:
            d = datetime.now()
            str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
            file_ma200.write("%s,%s\r\n" % (str_d,ma_data))

    if not STATUS_FLAG_DICT['sd']:
        d = datetime.now()
        str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
        if SD_NUM_OF_READS != 0:
            file_sd.write("%s,%.3f,%.3f\r\n" % (str_d,SD_SUM/SD_NUM_OF_READS,SD_MAX))
        SD_SUM = 0
        SD_NUM_OF_READS = 0
        SD_MAX = 0

    ch0 = mcp.read_adc(ADC_CO2_PIN)
    avoltage_co2 = float(ch0/1024.00 * 5.0)
    ch2 = mcp.read_adc(ADC_FLOW_PIN)
    avoltage_flow = float(ch2/1024.00 * 5.0)
    temperature, humidity, crc_check = am.sense()
    d = datetime.now()
    str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
    file_co2.write("%s,%d\r\n" % (str_d,avoltage_co2))
    file_flow.write("%s,%d\r\n" % (str_d, avoltage_flow))
    file_am.write("%s,%0.1f,%0.1f,%d\r\n" % (str_d,temperature,humidity,crc_check))

    if not STATUS_FLAG_DICT['aero']:
        res_list = aeroObject.command('3')
        if len(res_list) >= 6:
            most_recent_record = len(res_list) - 1
            aero_data = res_list[most_recent_record][0:10] + ',' + res_list[most_recent_record][11:]
            d = datetime.now()
            str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
            file_aero.write("%s,%s\r\n" % (str_d,aero_data))

    if STATUS_FLAG_DICT['aero'] == 1:
        print ("(ERR0R): STATUS FLAG for AERO == 1")
        disable_led()
    if STATUS_FLAG_DICT['sd'] == 1:
        print ("(ERROR): STATUS FLAG for SD == 1")
        disable_led()
    if STATUS_FLAG_DICT['ma200'] == 1:
        print ("(ERROR): STATUS FLAG for MA200 == 1")
        disable_led()

def fixAero():
    print ("(AEROCET531s): Fixing the serial connection...")
    aeroObject.close()
    aeroObject.open()
def fixSd():
    print ("(SD4023): Fixing the serial connection...")
    sdObject.close()
    sdObject.open()
def fixMA200():
    print ("(MA200): Fixing the serial connection...")
    sdObject.close()
    sdObject.open()

def sd_thread():
    global SD_SUM
    global SD_MAX
    global SD_NUM_OF_READS

    if NUM_MIN_RUN is None:
        tsd = threading.Timer(1.0,sd_thread)
        tsd.setDaemon(True)
        tsd.start()
    elif NUM_MIN_RUN >= 0:
        tsd = threading.Timer(1.0,sd_thread)
        tsd.setDaemon(True)
        tsd.start()
    else:
        close_connections()

    if not sdObject.get_status():
        decibel = sdObject.read_decibel()
        if decibel is not None:
            SD_SUM = SD_SUM + decibel
            SD_NUM_OF_READS += 1
        if decibel > SD_MAX:
            SD_MAX = decibel

def disable_led():
    print ("Disable flag led")
    GPIO.output(STATUS_LED_PIN,0)

def close_connections():
    sdObject.close()
    maObject.close()
    aeroObject.close()
    print ("Stopping")
    os._exit

def main():
    current_retry_number = 0

    '''
    while current_retry_number < MAX_NUM_RETRIES:
        try:
            sdObject.open()
            aeroObject.open()
            maObject.open()
            print ("SUCCESS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        except IOError as e:
            current_retry_number += 1
            sdObject.close()
            aeroObject.close()
            maObject.close()
            print (e)
            print ("ERROR: Recieved IOError exception, retrying...")

            continue
        break
    '''
    sdObject.open()
    aeroObject.open()
    maObject.open()

    if current_retry_number != MAX_NUM_RETRIES:
        file_sd.write('#'*10)
        file_sd.write('\r\n')
        file_aero.write('#'*10)
        file_aero.write('\r\n')
        file_co2.write('#'*10)
        file_co2.write('\r\n')
        file_flow.write('#'*10)
        file_flow.write('\r\n')
        file_am.write('#'*10)
        file_am.write('\r\n')
        file_ma200.write('#'*10)
        file_ma200.write('\r\n')

        aero_activate_thread()
        sd_thread()
        main_thread()
    else:
        print ("Could not open serial ports!")
        GPIO.output(STATUS_LED_PIN,0)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ("Cleaning up GPIO")
