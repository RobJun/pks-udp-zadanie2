import threading
import time
from src.constants import ACK, TEXT,FIN, encapsulateData, parseData

from src.connection import Connection

class serverThread(threading.Thread):
    def __init__(self,connection : Connection):
        threading.Thread.__init__(self)
        self.con = connection

    def run(self):
        print("---- SERVER LISTEN THREAD START----")
        awaitedWindow = 0
        fileName =""
        buildFile = b""
        buildText = ""
        while True:
            if self.con.getRunning():
                d = self.con.recieve()
                if d != None:
                    msg,addr = d; 
                    #print(msg)
                    msg = parseData(msg)
                    #print([(key,val) for key,val in msg.items()])
                    #print(awaitedWindow == int.from_bytes(msg["seqNum"],"big"))
                    if int.from_bytes(msg["seqNum"],"big") == awaitedWindow:
                        awaitedWindow += 1
                        self.con.socket.sendto(encapsulateData(0x00,ACK,0,int.from_bytes(msg["seqNum"],"big"),b""),addr)
                        if msg["type"] == TEXT:
                            buildText += msg["data"].decode()
                            if msg["flags"] == FIN:
                                print(buildText)
                                buildText = ""
                        elif msg["type"] == 0x02:
                            if msg["flags"] == 0x01:
                                fileName = msg["data"].decode()
                            elif msg["flags"] == 0x02:
                                f = open(fileName, "wb")
                                f.write(buildFile)
                            else:
                                buildFile += msg["data"]

                    if awaitedWindow == self.con.maxWindowSize:
                        awaitedWindow = 0
                
            else:
                break


class clientSendThread(threading.Thread):
    def __init__(self,connection : Connection):
        threading.Thread.__init__(self)
        self.con = connection
    
    def run(self):
        print("---- CLIENT SENDING THREAD START----")
        sendFirst = False
        while True:
            if self.con.getRunning():
                if self.con.sendNext():
                    if not sendFirst:
                        self.con.changeState(0,True)
                        sendFirst = True
                    #print("sending {} frame".format(self.con.getCurrentWindowSize()-1))
                if self.con.checkTime():
                    if self.con.resendWindow():
                        print("resending window")
                        self.con.rstTime()
            else:
                break

class clientListenThread(threading.Thread):
    def __init__(self,connection : Connection):
        threading.Thread.__init__(self)
        self.con = connection

    def run(self):
        print("---- CLIENT LISTEN THREAD START----")
        while True:
            if self.con.getRunning():
                recv = self.con.recieve()
                if recv != None:
                    msg, addr = recv
                    msg = parseData(msg)
                    self.con.ack(int.from_bytes(msg["ackNum"],"big"))
            else:
                break