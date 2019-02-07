from threading import Thread
import time
import serial
import datetime

##### Settings for the user to change #####

#Device setup
serialPort = '/dev/ttyUSB0'
reverseD6T = True

# Intervals
pLogFile = 1 # Interval between logfile writes

#Detection parameters
TargetDev = 1.8 # This is the deviation that should trigger a human presence alert
TargetTolerance = 1 # This is the tolerance for when the current value drops below the registered value

TargetTemp = 18 # Temperature to consider a human, above this we will consider it a person

#CSV file writing
filePath = "/var/www/html/logfile.csv" # Full file path, properly escaped
filePathDetail = "/var/www/html/logfile-detail.csv" # Full file path, properly escaped

# !!! Make sure the script has permissions to write to these folders !!!

#Functionality setup
debug = False # If this is enabled the script will output the values being read to the console
csv_on = True

### Excel does not meet the csv standards. To correctly import in Excel either:
## 1. Add SEP=, in the first line (not required for other softwares, will appear as a value in other softwares)
## 2. Change the extension to .txt and run the Text Importing Assistant

##### End of Settings #####
valsDetail = [0] * 8
dhLastSensorVals = [[0,0,0]]
for i in range(7):
        dhLastSensorVals.append([0,0,0])
dhLastSensorValsWrites = 0
dhPresence = [0,0,0,0,0,0,0,0]
dhPresenceTemp = [0,0,0,0,0,0,0,0]
valPTAT = 0
connected = False
notKill = True

class DetectHuman():
        def updateCelVals(self, argCel, argVal):
                global dhLastSensorValsWrites
                dhLastSensorVals[argCel].pop(0)
                dhLastSensorVals[argCel].append(argVal)
                if dhLastSensorValsWrites <=25:
                        dhLastSensorValsWrites += 1

        def checkHuman(self, argCell):
                global dhLastSensorValsWrites
                global TargetTemp
                if dhLastSensorValsWrites>20: #we're discarding more values as there seems to be some delay starting the sensor
                        isPerson = False
                        if int(dhLastSensorVals[argCell][2])>TargetTemp:
                                isPerson = True
                        if isPerson:
                                dhPresence[argCell] = 1
                        else:
                                dhPresence[argCell] = 0

        def checkEntranceCell(self, argCel):
                global dhLastSensorValsWrites
                if dhLastSensorValsWrites>20: #we're discarding more values as there seems to be some delay starting the sensor
                        dev = self.calcHDifToLastVal(dhLastSensorVals[argCel])
                        isPerson = False
                        if dev > TargetDev:
                                isPerson = True
                        if isPerson:
                                dhPresence[argCel] = 1
                                dhPresenceTemp[argCel] = dhLastSensorVals[argCel][len(dhLastSensorVals[argCel])-1]
                                self.normaliseCellVals(argCel)

        def checkExitCell(self, argCel):
                global dhLastSensorValsWrites
                if dhLastSensorValsWrites>20 and dhPresence[argCel] == 1:
                        dev = self.calcHDifToLastVal(dhLastSensorVals[argCel], True)
                        isPerson = True
                        if dev < (TargetDev*-1):
                                isPerson = False
                        if isPerson == False:
                                dhPresence[argCel] = 0
                                self.normaliseCellVals(argCel)

        def checkPresence(self, argCel):
                global dhLastSensorValsWrites
                if dhLastSensorValsWrites>20 and dhPresence[argCel] == 1 and \
                int(dhLastSensorVals[argCel][len(dhLastSensorVals[argCel])-1]) < int(dhPresenceTemp[argCel]) - TargetTolerance:
                                dhPresence[argCel] = 0

        def normaliseCellVals(self, argCel):
                val = dhLastSensorVals[argCel][2]
                dhLastSensorVals[argCel][0] = val
                dhLastSensorVals[argCel][1] = val

        def calcHDifToLastVal(self, arg, negative=False):
                dif = [0] * (len(arg) - 1)
                for d in range(len(arg)-1):
                        dif[d] = int(arg[len(arg)-1])-int(arg[d])
                result = 0
                if negative:
                        result = min(dif)
                else:
                        result = max(dif)
                return result

class DataProcessing():
        def addToFile(self, filepath, txt):
                F = open(filepath, 'a')
                F.write(txt)
        
        def buildCsvString(self, time, values):
                finalString = time + ','
                for x in range(len(values)):
                        if x < len(values)-1:
                                finalString += str(values[x]) + ','
                        else:
                                finalString += str(values[x])
                finalString += '\n'
                return finalString

## Thread classes
class SerialThread(Thread):
 
    def __init__(self):
        Thread.__init__(self)
        
    def run(self):
        while True:
            print("Attempting to connect")
            try:
                global serialPort
                conn = serial.Serial(serialPort, 9600)
                break
            except serial.SerialException as e:
                print("Fail to connect: {}".format(e))
                time.sleep(3)
        time.sleep(2)

        print("Listening")

        global notKill
        while notKill:
                global valPTAT
                ler = conn.readline().decode()
                ler = ler.strip()
                temp = ler.split(",")
                for i in range(8):
                        valsDetail[i] = temp[i]
                if(reverseD6T):
                        valsDetail.reverse()
                valPTAT = temp[8]

                global connected
                connected = True
            
                if debug:
                    print("Values: {}".format(valsDetail))
                    print("PTAT Value: {}".format(valPTAT))
        conn.close()


class DataThread(Thread):
 
    def __init__(self):
        Thread.__init__(self)
        
    def run(self):
        global notKill
        while notKill:
                ts = time.time()
                st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d,%H:%M:%S')
                day = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

                printVals = []
                printVals.extend(valsDetail)
                printVals.append(valPTAT)
                stringPrintDetail = DataProcessing().buildCsvString(st, printVals)
                stringPrintNormal = DataProcessing().buildCsvString(st, dhPresence)

                fpDetFinal = filePathDetail[:-4] + day + ".csv"
                fpFinal = filePath[:-4] + day + ".csv"

                #Writing the new line in the file
                if csv_on:
                        DataProcessing().addToFile(fpDetFinal, stringPrintDetail)
                        DataProcessing().addToFile(fpFinal, stringPrintNormal)

                ## Add this all to the same file?
                ## Need a way to process this into the table as a annotation

                #Waiting for the interval so we don't write too fast
                time.sleep(pLogFile)

class DetectHumanThread(Thread):
        def __init__(self):
                Thread.__init__(self)
        
        def run(self):
                global notKill
                while notKill:
                        for i in range(8):
                                DetectHuman().updateCelVals(i, valsDetail[i])
                                DetectHuman().checkHuman(i)
                                #DetectHuman().checkEntranceCell(i)
                                #DetectHuman().checkExitCell(i)
                                #DetectHuman().checkPresence(i)
                                
                        time.sleep(pLogFile)

## Main routine
if __name__ == '__main__':
        thread1 = SerialThread()
        thread1.setName('Thread 1')
        thread1.start()
        
        while True:
                if connected:
                        thread2 = DataThread()
                        thread2.setName('Thread 2')

                        thread3 = DetectHumanThread()
                        thread3.setName('Thread 3')

                        thread2.start()
                        thread3.start()

                        break

        #Locking mainthread while thread1 is still alive
        #This means the program won't terminate until thread1 crashes or
        #until we catch the KeyboardInterrupt that will signal
        #every thread to kill itself correctly
        try:
                while(thread1.is_alive):
                        time.sleep(1)        
        except KeyboardInterrupt:
                print("Stopping every task")
                notKill=False

        print('Program closing')
