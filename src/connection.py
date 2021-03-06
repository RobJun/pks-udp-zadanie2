import socket
import threading
import time
from src.constants import EMPTY, HEADER_SIZE, MAX_SEQ, checkCRC16, encapsulateData,FIN, simulateMistake,parseData,CRC_SIZE


class Connection:
    def __init__(self,socket : socket.socket, server : bool = False):
        self.socket = socket
        self.running = True 
        self.server = server
        self.addr = 0
        self.connected = False
        self.end = False

        #tries for initialization
        self.initPacket = False
        self.initTries = 0
        self.maxTries = 3


        #for recieving keep alive
        self.keepAliveAwait = False
        self.keepAliveAwaitStartTime = 0 #seconds

        #for sending keep alive
        self.keepAliveSend = False
        self.keepAliveSendStartTime = 0 #seconds
        self.keepAliveFirstFrame = True

        # retries of keep alive
        self.keepAliveTries = 0
        self.keepAliveMaxTries = 3

        self.waitingForKeepAck = False

        self.windowCondtion = threading.RLock()    
        self.closeEvent = threading.Event()  
        
        self.packetsToSend = []
        self.maxWindowSize = 1 if not server else 5
        self.windowSize = 1
        self.timeoutTime = 5 #seconds
        self.startTime = 0
        self.fsize = 1024


        self.simulateMistake = True
        self.simulate = simulateMistake

        self.maxTimeOuts = 4
        self.resendTries = 0

        self.awaitedWindow = 0

        self.lastSeq = -1

        self.lastSendFrame = None

        self.sending = 0 # 0 - undetermined; 1 - listening; 2 - sending


        self.packetsGroups = []
        self.numberOfDataFrames = 0
        self.packeTGroupStart = False


    def enableKeepAliveAwait(self):
        with self.windowCondtion:
            self.keepAliveAwait = True
            self.rstTimeAliveClock(True)

    def enableKeepAliveSend(self):
        with self.windowCondtion:
            self.keepAliveSend = True
            self.keepAliveFirstFrame = True
            self.rstTimeAliveClock(False)

    def disableKeepAlive(self):
        with self.windowCondtion:
            self.keepAliveAwait = False
            self.keepAliveSend = False
            self.keepAliveFirstFrame = True
            self.waitingForKeepAck = False

    def checkTime(self):
        with self.windowCondtion:
            t = time.time() - self.startTime
            return t >= self.timeoutTime

    def rstTime(self):
        with self.windowCondtion:
            self.startTime = time.time()

    def rstTimeAliveClock(self, what):
        if what:
            with self.windowCondtion:
                self.keepAliveAwaitStartTime = time.time()
        else:
            with self.windowCondtion:
                self.keepAliveSendStartTime = time.time()
    
    def checkKeepAliveTimer(self,which : bool,t : int):
        if which:
            with self.windowCondtion:
                return (time.time() - self.keepAliveAwaitStartTime) >= t
        else:
            with self.windowCondtion:
                return (time.time() - self.keepAliveSendStartTime) >= t


    def getConnected(self):
        with self.windowCondtion:
            return self.connected

    def getCurrentWindowSize(self):
        with self.windowCondtion:
            return self.windowSize

    def transferDone(self):
        with self.windowCondtion:
            return len(self.packetsToSend) == 0


    def getRunning(self):
        with self.windowCondtion:
            return self.running

    def changeState(self,typ, val):
        if typ == 0:
            with self.windowCondtion:
                self.connected = val
        elif typ == 1:
            with self.windowCondtion:
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

    def sendMultiple(self,typ : int, flags : int, fragCount : int, fragments : list):
        with self.windowCondtion:
            self.packetsGroups.append([0,len(fragments)])
            self.numberOfDataFrames += len(fragments)
        count = 0
        msg = self.send(typ,flags,fragCount,b'',0)
        i = 1
        for frag,size in fragments:
            with self.windowCondtion:
                msg = self.send(typ,flags,i,frag,size)
                if count == 0:
                    self.packetsGroups[-1].append(msg)
            count=1
            i+=1

    def send(self,type : int,flags : int,fragCount : int,data : bytes, size : int = 0):
        with self.windowCondtion:
            seqNum = self.lastSeq = (self.lastSeq+1) % MAX_SEQ
            msg = encapsulateData(type,flags,seqNum,fragCount,data,size)
            self.packetsToSend.append((seqNum,msg))
            if len(self.packetsToSend) == 1:
                self.rstTime()
            #print(self.packetsToSend)
            return msg

    def getFlagsOfTop(self):
        with self.windowCondtion:
            if len(self.packetsToSend) > 0:
                return parseData(self.packetsToSend[0][1])["flags"]
            return EMPTY
    
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
                    #self.enableKeepAlive()
                
                removed = self.packetsToSend.pop(0)
                result = True
                self.windowSize -= 1
                self.startTime = time.time()
                #print(self.packetsToSend)
                return result,removed
            return result, None;

    def resendWindow(self, timeout):
        resend = False
        with self.windowCondtion:
            if timeout and self.keepAliveSend:
                self.keepAliveTries +=1
                if self.keepAliveTries == self.keepAliveMaxTries:
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
                if self.resendTries == self.maxTimeOuts:
                    if self.server:
                        self.addr = 0
                    print("other side not responding")
                    self.flushConnection()
                    return resend;
            if len(self.packetsToSend) != 0:
                for i in range(self.windowSize-1):
                    frame = self.packetsToSend[i][1];
                    #if self.simulateMistake:
                    #   frame = self.simulate(frame)
                    try:
                        self.socket.sendto(frame,self.addr)
                    except IOError:
                        pass
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
                    frame = self.simulate(frame,self.numberOfDataFrames)
                try:
                    self.socket.sendto(frame,self.addr)
                except IOError:
                    pass
            ##print("sent frame: ", frame)
                self.lastSendFrame = frame
                self.windowSize +=1
                sent = True
        return sent;

    def flushConnection(self, notSwap = True):
        with self.windowCondtion:
                self.packetsToSend = []
                self.packetsGroups = []
                if notSwap:
                    self.changeState(0,False)
                    self.windowSize = 1
                self.initTries = 0
                self.resendTries = 0
                self.keepAliveTries = 0
                self.lastSeq = -1
                self.lastSendFrame = None
                if notSwap:
                    if self.server:
                        self.sending = 1
                        self.addr = 0
                        self.awaitedWindow = 0
                    else:
                         self.sending = 2
                self.disableKeepAlive()
                if self.end:
                    self.closeEvent.set()


    def canSend(self):
        return self.sending == 2


    def lengthOfGroup(self):
        with self.windowCondtion:
            return self.packetsGroups[0][1]

    def moveToNextPacketGroup(self):
        with self.windowCondtion:
            if self.packetsGroups[0][0] == self.packetsGroups[0][1]:
                self.packeTGroupStart = False
                self.numberOfDataFrames -= self.packetsGroups[0][1]
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



