import threading
import time
import sys
import os
import os.path
from datetime import datetime
sys.path.insert(0, './lib/Met-One-Aerocet-531s-serial/')
sys.path.insert(0, './lib/REED-SD-4023-serial/')
sys.path.insert(0, './lib/AethLabs-MA200-serial/')
from sd_4023 import SD_4023
from aerocet531s import Aerocet531s
from ma200 import MA200
import Adafruit_GPIO.SPI as SPI
from Adafruit_MCP3008 import MCP3008
import getdevices
#import RPi.GPIO as GPIO

usb_paths = getdevices.serial_ports('/dev/sd*')
for i in usb_paths:
    print i

if len(usb_paths) > 0:
    PATH_TO_USB = '/media/usb0/'
else:
    PATH_TO_USB = ''

#Redirection all print statments to a log file
timestr = PATH_TO_USB + time.strftime("%Y%m%d-%H%M%S") + "_debug.log"
sys.stdout = open(timestr,"w")

###CONSTANTS####
_DEBUGVAR_ = True
AERO_FILE_NAME = PATH_TO_USB + 'output_aerocet531.log'
SD_FILE_NAME = PATH_TO_USB + 'output_sd4023.log'
CO2_FILE_NAME = PATH_TO_USB + 'output_co2.log'
FLOW_FILE_NAME = PATH_TO_USB + 'output_flow.log'
TMP_FILE_NAME = PATH_TO_USB + 'output_tmp36.log'
MA200_FILE_NAME = PATH_TO_USB + 'output_ma200.log'
MAX_NUM_RETRIES = 5
CLK = 18
MISO = 23
MOSI = 24
CS = 25
ADC_CO2_PIN = 0
ADC_FLOW_PIN = 2
ADC_TMP_PIN = 4
NUM_MIN_RUN = 5
#STATUS_LED_PIN = 5 #RPi GPIO_5

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
                      'tmp':'Date,Time,Temp(Celsius)\r\n',
                      'flow':'Date,Time,Analog_Voltage\r\n'}
###ENDCONSTANTS####

###GLOBALS####
SD_SUM = 0
SD_NUM_OF_READS = 0
SD_MAX = 0
'''
Status flag dictionary is used to check if the status of each Instrument
At the end of the main thread, we check to make sure all the values in our
status flag dictionary are zeros. If any are 1, then we will try to reestablish
a connection with the device
'''
STATUS_FLAG_DICT = {'aero':0,'sd':0,'ma200':0}
###ENDGLOBALS####


#GPIO.setmode(GPIO.BCM)
#GPIO.setup(STATUS_LED_PIN,GPIO.OUT)
#GPIO.output(STATUS_LED_PIN,0)


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

#the 0 indicates unbuffered, therefore it will always write to file immediately
file_aero = open(AERO_FILE_NAME,"a",0)
file_sd = open(SD_FILE_NAME,"a",0)
file_co2 = open(CO2_FILE_NAME,"a",0)
file_flow = open(FLOW_FILE_NAME,"a",0)
file_tmp = open(TMP_FILE_NAME,'a',0)
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
if os.path.getsize(TMP_FILE_NAME) == 0:
    print ("(TMP): Empty output log. Writing header")
    file_tmp.write(OUTPUT_LOG_HEADERS['tmp'])
if os.path.getsize(MA200_FILE_NAME) == 0:
    print ("(MA200): Empty output log. Writing header.")
    file_ma200.write(OUTPUT_LOG_HEADERS['ma200'])

def aero_activate_thread():
    if not aeroObject.get_status():
        aeroObject.activate_comm_mode()
    threading.Timer(55.0,aero_activate_thread).start()
    tactive = threading.Timer(55.0,aero_activate_thread)
    tactive.setDaemon(True)
    tactive.start()

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
        NUM_MIN_RUN -= 1
        tmain = threading.Timer(59.0,main_thread)
        tmain.setDaemon(True)
        tmain.start()
    else:
        #aeroObject.stop_aero_sampling()
        close_connections()

    STATUS_FLAG_DICT['aero'] = aeroObject.get_status()
    STATUS_FLAG_DICT['sd'] = sdObject.get_status()
    STATUS_FLAG_DICT['ma200'] = maObject.get_status()

    if not STATUS_FLAG_DICT['sd']:
        d = datetime.now()
        str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
        file_sd.write("%s,%.3f,%.3f\r\n" % (str_d,SD_SUM/SD_NUM_OF_READS,SD_MAX))
        SD_SUM = 0
        SD_NUM_OF_READS = 0
        SD_MAX = 0

    if not STATUS_FLAG_DICT['aero']:
        res_list = aeroObject.command('3')
        if len(res_list) >= 6:
            most_recent_record = len(res_list) - 1
            aero_data = res_list[most_recent_record][0:10] + ',' + res_list[most_recent_record][11:]
            d = datetime.now()
            str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
            file_aero.write("%s,%s\r\n" % (str_d,aero_data))
            #Old way
            '''
            most_recent_record = len(res_list) - 1
            rec_time = res_list[most_recent_record][0:19]
            rec_PM1 = res_list[most_recent_record][20:25]
            rec_PM2_5 = res_list[most_recent_record][26:31]
            rec_PM4 = res_list[most_recent_record][32:37]
            rec_PM7 = res_list[most_recent_record][38:43]
            rec_PM10 = res_list[most_recent_record][44:49]
            rec_TSP = res_list[most_recent_record][50:55]
            rec_LOC = res_list[most_recent_record][58:61]
            rec_SEC = res_list[most_recent_record][62:65]
            rec_STA = res_list[most_recent_record][66:69]
            d = datetime.now()
            str_d = d.strftime('%Y-%m-%d %H:%M:%S:%f')
            file_aero.write("%s %s %s %s %s %s %s %s %s %s %s\n" %(str_d,rec_time,rec_PM1,rec_PM2_5,rec_PM4,rec_PM7,rec_PM10,rec_TSP,rec_LOC,rec_SEC,rec_STA))
            '''

    if not STATUS_FLAG_DICT['ma200']:
        ma_data = maObject.read()
        if ma_data is not None:
            d = datetime.now()
            str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
            file_ma200.write("%s,%s\r\n" % (str_d,ma_data))

    ch0 = mcp.read_adc(ADC_CO2_PIN)
    ch2 = mcp.read_adc(ADC_FLOW_PIN)
    ch4 = mcp.read_adc(ADC_TMP_PIN)
    ch4 = ( ( (ch4 / 1024.0) * 5.0 * 1000.0) - 500.0) / 10.0
    d = datetime.now()
    str_d = d.strftime('%Y-%m-%d,%H:%M:%S:%f')
    file_co2.write("%s,%d\r\n" % (str_d,ch0))
    file_flow.write("%s,%d\r\n" % (str_d, ch2))
    file_tmp.write("%s,%f\r\n" % (str_d,ch4))

    if STATUS_FLAG_DICT['aero'] == 1:
        #We have an error, try restarting the serial connection to the aero
        print ("(ERR0R): STATUS FLAG for AERO == 1")
        enable_led()
        #fixAero()
    if STATUS_FLAG_DICT['sd'] == 1:
        #We have an error, try restarting the serial connected to the sd
        print ("(ERROR): STATUS FLAG for SD == 1")
        enable_led()
        #fixSd()
    if STATUS_FLAG_DICT['ma200'] == 1:
        print ("(ERROR): STATUS FLAG for MA200 == 1")
        enable_led()
        #fixMA200()

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

def enable_led():
    print ("Enable flag led")
    #GPIO.output(STATUS_LED_PIN,1)
    #time.sleep(0.2)
    #GPIO.output(STATUS_LED_PIN,0)

def close_connections():
    sdObject.close()
    maObject.close()
    aeroObject.close()
    print ("Stopping")
    os._exit

def main():
    current_retry_number = 0

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
    if current_retry_number != MAX_NUM_RETRIES:
        file_sd.write('#'*10)
        file_sd.write('\r\n')
        file_aero.write('#'*10)
        file_aero.write('\r\n')
        file_co2.write('#'*10)
        file_co2.write('\r\n')
        file_flow.write('#'*10)
        file_flow.write('\r\n')
        file_tmp.write('#'*10)
        file_tmp.write('\r\n')
        file_ma200.write('#'*10)
        file_ma200.write('\r\n')

        #aeroObject.start_aero_sampling()
        aero_activate_thread()
        sd_thread()
        main_thread()
    else:
        print ("Could not open serial ports!")
        #GPIO.output(STATUS_LED_PIN,1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ("Cleaning up GPIO")
        #GPIO.cleanup()

#consider throwing the start and stop aero sampling functions into the class
