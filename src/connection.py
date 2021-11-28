import socket
import threading
import time
import random

from src.constants import MAX_SEQ, checkCRC16, encapsulateData,FIN, simulateMistake


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
        self.keepAliveFirstFrame = True
        self.keepAliveTries = 0
        self.keepAliveMaxTries = 3
        self.keepAliveStartTime = 15 #seconds
        self.server = server
        self.keepAliveTime = 15;


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
        self.simulate = simulateMistake

        self.maxTimeOuts = 7
        self.resendTries = 0

        self.awaitedWindow = 0

        self.lastSeq = -1

        self.lastSendFrame = None

        self.sending = 0 # 0 - undetermined; 1 - listening; 2 - sending


        self.packetsGroups = []
        self.packeTGroupStart = False


    def enableKeepAlive(self):
        with self.keepAliveTimeLock:
            self.keepAlive = True
            self.keepAliveFirstFrame = True
            self.rstTimeAliveClock()

    def disableKeepAlive(self):
        with self.keepAliveTimeLock:
            self.keepAlive = False
            self.keepAliveFirstFrame = True

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
    
    def checkKeepAliveTimer(self,t : int):
        with self.keepAliveTimeLock:
            return (time.time() - self.keepAliveStartTime) >= t


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

    def sendMultiple(self,typ : int, flags : int, ackNum : int, fragments : list, lastisFin : bool = False):
        with self.windowCondtion:
            self.packetsGroups.append([0,len(fragments)])
        count = 0
        if not lastisFin:
            for frag,size in fragments:
                msg = self.send(typ,flags,None,ackNum,frag,size)
                if count == 0:
                    with self.windowCondtion:
                        self.packetsGroups[-1].append(msg)
                count=1
        else:
            for frag,size in fragments[:-1]:
                msg = self.send(typ,flags,None,ackNum,frag,size)
                if count == 0:
                    with self.windowCondtion:
                        self.packetsGroups[-1].append(msg)
                count=1
            msg= self.send(typ,flags | FIN,None,ackNum,fragments[-1][0],fragments[-1][1])
            if count == 0:
                with self.windowCondtion:
                    self.packetsGroups[-1].append(msg)
            count=1

    def send(self,type : int,flags : int, seqNum : int ,ackNum : int,data : bytes, size : int = 0):
        with self.windowCondtion:
            seqNum = self.lastSeq = (self.lastSeq+1) % MAX_SEQ
            msg = encapsulateData(type,flags,seqNum,ackNum,data,size)
            self.packetsToSend.append((seqNum,msg))
            self.fragCount +=1
            if len(self.packetsToSend) == 1:
                self.rstTime()
            #print(self.packetsToSend)
            return msg
    
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
                    self.enableKeepAlive()
                
                removed = self.packetsToSend.pop(0)
                result = True
                self.windowSize -= 1
                self.currentFrag +=1
                self.startTime = time.time()
                #print(self.packetsToSend)
                return result,removed
            return result, None;

    def resendWindow(self, timeout):
        resend = False
        with self.windowCondtion:
            if timeout and self.keepAlive:
                self.keepAliveTries +=1
                if self.keepAliveTries == self.keepAliveMaxTries + 1:
                    print("keep alive -- no response")
                    self.flushConnection()
                    return resend;
            elif timeout and self.initPacket:
                self.initTries+=1
                if self.initTries == self.maxTries + 1:
                    print("Couldn't connect")
                    if self.server:
                        self.addr = 0
                    self.flushConnection()
                    return resend;
            elif timeout and self.resendTries <= self.maxTimeOuts:
                self.resendTries+=1
                if self.resendTries == self.maxTimeOuts + 1:
                    if self.server:
                        self.addr = 0
                    print("other side not responding")
                    self.flushConnection()
                    return resend;
            if len(self.packetsToSend) != 0:
                for i in range(self.windowSize-1):
                    frame = self.packetsToSend[i][1];
                    if self.simulateMistake:
                        frame = self.simulate(frame)
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
                if self.simulateMistake:
                    frame = self.simulate(frame)
                self.socket.sendto(frame,self.addr)
                self.lastSendFrame = frame
                self.windowSize +=1
                sent = True
        return sent;

    def flushConnection(self, swap = True):
        with self.windowCondtion:
                self.packetsToSend = []
                self.packetsGroups = []
                if swap:
                    self.changeState(0,False)
                self.initTries = 0
                self.resendTries = 0
                self.keepAliveTries = 0
                self.lastSeq = -1
                self.fragCount = 0
                self.lastSendFrame = None
                if swap:
                    if self.server:
                        self.sending = 1
                    else:
                         self.sending = 2
                if swap:
                    self.disableKeepAlive()

    def canSend(self):
        return self.sending == 2


    def lengthOfGroup(self):
        with self.windowCondtion:
            return self.packetsGroups[0][1]

    def moveToNextPacketGroup(self):
        with self.windowCondtion:
            if self.packetsGroups[0][0] == self.packetsGroups[0][1]:
                self.packeTGroupStart = False
                self.packetsGroups.pop(0)
    def getCountedGroups(self):
        with self.windowCondtion:
            return self.packetsGroups[0][0]

    def enablePacketGroup(self,data):
        with self.windowCondtion:
            if not self.packeTGroupStart and len(self.packetsGroups) != 0:
                if data ==  self.packetsGroups[0][2]:
                    self.packeTGroupStart = True;
                    return True;
                else:
                    return False;
            else:
                if len(self.packetsGroups) == 0:
                    return False
                return True

    def incrementGroup(self):
        with self.windowCondtion:
             self.packetsGroups[0][0]+=1



