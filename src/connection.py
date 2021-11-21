import socket
import threading
import time

from src.constants import checkCRC16, encapsulateData


class Connection:
    def __init__(self,socket : socket.socket):
        self.socket = socket
        self.running = True 
        self.addr = 0
        self.connected = False


        self.connectedCondition = threading.RLock()
        self.runningCondition = threading.RLock()
        self.timeCondition = threading.RLock()
        self.windowCondtion = threading.RLock()
        
        self.packetsToSend = []
        self.maxWindowSize = 5
        self.windowSize = 1
        self.timeoutTime = 10 #seconds
        self.startTime = 0
        self.fsize = 1024

    def checkTime(self):
        with self.timeCondition:
            t = time.time() - self.startTime
            result = t >= self.timeoutTime 
            return result

    def rstTime(self):
        with self.timeCondition:
            self.startTime = time.time()

    def getConnected(self):
        with self.connectedCondition:
            return self.connected

    def getCurrentWindowSize(self):
        with self.windowCondtion:
            return self.windowSize


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
                return msg,addr
        except Exception:
            return  None
        return None

    def send(self,type : int,flags : int, seqNum : int ,ackNum : int,data : bytes):
        with self.windowCondtion:
            if len(self.packetsToSend) != 0:
                seqNum = (self.packetsToSend[-1][0] + 1) % self.maxWindowSize
            else:
                 seqNum = 0
                 self.rstTime()
            msg = encapsulateData(type,flags,seqNum,0,data)
            self.packetsToSend.append((seqNum,msg))
    
    def ack(self, seqNum):
        with self.windowCondtion:
            if seqNum == self.packetsToSend[0][0]:
                self.packetsToSend = self.packetsToSend[1:]
                self.windowSize -= 1
                self.startTime = time.time()

    def resendWindow(self):
        resend = False
        with self.windowCondtion:
            if len(self.packetsToSend) != 0:
                for i in range(self.windowSize-1):
                    #print(self.packetsToSend[i][1])
                    self.socket.sendto(self.packetsToSend[i][1],self.addr)
                    resend = True
        return resend

    def sendNext(self):
        sent = False
        with self.windowCondtion:
            if len(self.packetsToSend) >= self.windowSize:
                frame = self.packetsToSend[self.windowSize-1][1];
                #print(frame, "\nink: ",self.windowSize)
                self.socket.sendto(frame,self.addr)
                self.windowSize +=1
                sent = True

        return sent;
