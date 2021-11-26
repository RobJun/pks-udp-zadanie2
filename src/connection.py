import socket
import threading
import time
import random

from src.constants import MAX_SEQ, checkCRC16, encapsulateData


class Connection:
    def __init__(self,socket : socket.socket, server : bool = False):
        self.socket = socket
        self.running = True 
        self.addr = 0
        self.connected = False

        self.initPacket = False
        self.initTries = 0
        self.maxTries = 3


        self.keepAlive = False
        self.keepAliveTries = 0
        self.keepAliveMaxTries = 3
        self.keepAliveStartTime = 15 #seconds
        self.server = server
        self.keepAliveTime = 0;


        self.connectedCondition = threading.RLock()
        self.runningCondition = threading.RLock()
        self.timeCondition = threading.RLock()
        self.windowCondtion = threading.RLock()      
        self.keepAliveTimeLock = threading.RLock()
        
        self.packetsToSend = []
        self.maxWindowSize = 1
        self.windowSize = 1
        self.timeoutTime = 5 #seconds
        self.startTime = 0
        self.fsize = 1024

        self.fragCount = 0;
        self.currentFrag = 0;
        self.simulateMistake = True

        self.maxTimeOuts = 7
        self.resendTries = 0

        self.awaitedWindow = 0

        self.lastSeq = -1

        self.lastSendFrame = None

        self.sending = 0 # 0 - undetermined; 1 - listening; 2 - sending

    def checkTime(self):
        with self.timeCondition:
            t = time.time() - self.startTime
            return t >= self.timeoutTime

    def rstTime(self):
        with self.timeCondition:
            self.startTime = time.time()

    def rstTimeAliveClock(self):
        with self.keepAliveTimeLock:
            self.keepAliveStartTime = time.time()
    
    def checkKeepAliveTimer(self):
        with self.keepAliveTimeLock:
            return time.time() - self.keepAliveStartTime >= self.keepAliveTime


    def getConnected(self):
        with self.connectedCondition:
            return self.connected

    def getCurrentWindowSize(self):
        with self.windowCondtion:
            return self.windowSize

    def getCurrentFrags(self):
        with self.windowCondtion:
            return self.currentFrag

    def transferDone(self):
        with self.windowCondtion:
            return len(self.packetsToSend) == 0


    def getRunning(self):
        with self.runningCondition:
            return self.running

    def changeState(self,typ, val):
        if typ == 0:
            with self.connectedCondition:
                self.connected = val
        elif typ == 1:
            with self.runningCondition:
                self.running = val

    def recieve(self):
        try:
            msg,addr = self.socket.recvfrom(self.fsize)
            if checkCRC16(msg):
                return True,msg,addr
            else:
                return False,msg,addr
        except Exception:
            return  None
        return None

    def send(self,type : int,flags : int, seqNum : int ,ackNum : int,data : bytes):
        with self.windowCondtion:
            seqNum = self.lastSeq = (self.lastSeq+1) % MAX_SEQ
            msg = encapsulateData(type,flags,seqNum,0,data)
            self.packetsToSend.append((seqNum,msg))
            self.fragCount +=1
            if len(self.packetsToSend) == 0:
                self.rstTime()
            #print(self.packetsToSend)
    
    def ack(self, seqNum):
        with self.windowCondtion:
            result = False

            if len(self.packetsToSend) != 0 and seqNum == self.packetsToSend[0][0]:
                if self.initPacket:
                    self.initPacket = False
                    self.maxWindowSize = 5
                    self.tries = 0
                    self.resendTries = 0
                    self.changeState(0,True)
                self.packetsToSend = self.packetsToSend[1:]
                result = True
                self.windowSize -= 1
                self.currentFrag +=1
                self.startTime = time.time()
                #print(self.packetsToSend)
            return result;

    def resendWindow(self, timeout):
        resend = False
        with self.windowCondtion:
            if timeout and self.initPacket:
                self.initTries+=1
                if self.initTries == self.maxTries + 1:
                    print("Couldn't connect to server")
                    self.flushConnection()
                    return resend;
            elif timeout and self.resendTries <= self.maxTimeOuts:
                self.resendTries+=1
                if self.resendTries == self.maxTimeOuts + 1:
                    print("Server not responding")
                    self.flushConnection()
                    return resend;
            if len(self.packetsToSend) != 0:
                for i in range(self.windowSize-1):
                    frame = self.packetsToSend[i][1];
                    if self.simulateMistake and random.randint(0,50) == 0:
                        index = random.randint(0,len(frame)-1)
                        frame = frame[:index] + int.to_bytes(random.randint(0,255),1,"big") + frame[index+1:]
                    self.socket.sendto(frame,self.addr)
                    self.lastSendFrame = frame
                    resend = True
        return resend

    def sendNext(self):
        sent = False
        with self.windowCondtion:
            if self.addr == 0:
                print("NO connection to send")
                self.flushConnection()
                return 
            if self.windowSize != self.maxWindowSize+1 and len(self.packetsToSend) >= self.windowSize:
                frame = self.packetsToSend[self.windowSize-1][1];
                if self.simulateMistake and random.randint(0,50) == 0:
                    index = random.randint(8,len(frame)-1)
                    frame = frame[:index] + int.to_bytes(random.randint(0,255),1,"big") + frame[index+1:]
                self.socket.sendto(frame,self.addr)
                self.lastSendFrame = frame
                self.windowSize +=1
                sent = True
        return sent;

    def flushConnection(self):
        with self.windowCondtion:
                self.packetsToSend = []
                self.changeState(0,False)
                self.initTries = 0
                self.resendTries = 0
                self.lastSeq = -1
                self.fragCount = 0
                self.lastSendFrame = None

    def canSend(self):
        return self.sending == 2


