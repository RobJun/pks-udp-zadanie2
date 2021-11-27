import threading
import time
from src.constants import ACK, CONTROL, FILE, KEEP, RES, TEXT,FIN,SYN,MAX_SEQ,SWAP, encapsulateData, parseData,safePrint

from src.connection import Connection
from src.progressBar import printProgressBar


class clientSendThread(threading.Thread):
    def __init__(self,connection : Connection):
        threading.Thread.__init__(self)
        self.con = connection
        self.keepAliveTimeStart = time.time()
    
    def run(self):
        print("---- SENDING THREAD START ----")
        while True:
            if self.con.getRunning():
                if self.con.canSend():
                    if not self.con.transferDone():
                        self.con.sendNext()
                        #print("sending {} frame".format(self.con.getCurrentWindowSize()-1))
                        if self.con.checkTime():
                            if self.con.resendWindow(True):
                                safePrint("-> timeout -- resending window")
                                self.con.rstTime()
                if not self.con.server and self.con.keepAlive:
                    if (self.con.checkKeepAliveTimer(10) or self.con.keepAliveFirstFrame) and self.con.transferDone():
                        self.con.send(CONTROL,KEEP,None,0,b'')
                        self.con.rstTime()
                        self.con.rstTimeAliveClock()
                        self.con.keepAliveFirstFrame = False;
                        safePrint("-> sending keep alive")
                elif self.con.server and self.con.keepAlive and self.con.checkKeepAliveTimer(20):
                    self.con.addr = 0
                    self.con.awaitedWindow = 0
                    self.con.keepAlive = False;
                    self.con.flushConnection()
                    safePrint("server didnt recieve keep alive in time -- ending connection")
            else:
                print("---- SENDING THREAD END ----")
                break

class clientListenThread(threading.Thread):
    def __init__(self,connection : Connection, downloadDirectory = "./"):
        threading.Thread.__init__(self)
        self.con = connection
        self.downloadDirectory = downloadDirectory

    def run(self):
        print("---- LISTEN THREAD START ----")
        fileName =""
        buildFile = b""
        fragCount = 0;
        fragNums = 0;
        buildText = ""
        transferInit = 0
        poradie = 0
        while True:
            if self.con.getRunning():
                recv = self.con.recieve()
                if recv != None:
                    correct,msg, addr = recv
                    msg = parseData(msg)
                    if self.con.sending == 2 and msg["flags"] & ACK and correct:
                        if msg["flags"] == ACK | RES:
                            
                            safePrint("-> NACK recieved -- resending window\n")
                            self.con.resendWindow(False)
                            self.con.rstTime()
                        else:
                            corr, frame =  self.con.ack(int.from_bytes(msg["seqNum"],"big"))
                            if corr:
                                if self.con.enablePacketGroup(frame[1]):
                                    print("\r",end="")
                                    printProgressBar(self.con.getCountedGroups()+1,self.con.lengthOfGroup() , prefix = 'Frag sent:', suffix = 'Complete')
                                    self.con.incrementGroup()
                                    self.con.moveToNextPacketGroup()
                                if msg["type"] == CONTROL and  msg["flags"] == KEEP | ACK:
                                    safePrint("server keep alive accepted")
                                    self.con.rstTimeAliveClock()
                                elif msg["type"] == CONTROL and msg["flags"] == SWAP | ACK:
                                    safePrint("other side accepted swap")
                                    self.con.sending = 1
                                if self.con.transferDone() and not self.con.keepAlive:
                                    self.con.enableKeepAlive()
                    else:
                        if addr == self.con.addr or (self.con.addr == 0 and msg["type"] == CONTROL and msg["flags"] == SYN):
                            if not correct:
                                self.con.socket.sendto(encapsulateData(CONTROL,ACK|RES,int.from_bytes(msg["seqNum"],"big"),0,b""),addr)
                                safePrint("Bol prijaty chybny ramec -- posielam NACK")
                            elif recv[0] == b'':
                                pass;
                            else:
                                seq = int.from_bytes(msg["seqNum"],"big")
                                fragCount = int.from_bytes(msg["seqNum"],"big")
                                if seq < self.con.awaitedWindow:
                                    if msg["type"] == CONTROL:
                                        if ACK+msg["flags"] > 0x30:
                                            safePrint(msg)
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                elif seq == self.con.awaitedWindow:
                                    self.con.awaitedWindow += 1
                                    if msg["type"] == CONTROL:
                                        if ACK+msg["flags"] > 0x30:
                                            safePrint(msg)
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                        if msg["flags"] == SWAP:
                                            self.con.sending = 2;
                                            safePrint("you can now send files to: {}".format(addr[0]))
                                        elif msg["flags"] == SYN:
                                            self.con.addr = addr
                                            safePrint("Connection started with {}".format(addr[0]))
                                        elif msg["flags"] == FIN:
                                            self.con.awaitedWindow = 0
                                            self.con.addr = 0
                                            safePrint("Connection terminated with {}".format(addr[0]))
                                        elif msg["flags"] == KEEP:
                                            safePrint("Connection kept-alive with {}".format(addr[0]))
                                            self.con.rstTimeAliveClock()
                                            pass #reset timer
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                        if msg["type"] == TEXT:
                                            buildText += msg["data"].decode()
                                            self.con.disableKeepAlive()
                                            if msg["flags"] == FIN:
                                                self.con.enableKeepAlive()
                                                safePrint(buildText)
                                                buildText = ""
                                        elif msg["type"] == FILE:
                                            if msg["flags"] & SYN:
                                                transferInit = seq
                                                self.con.disableKeepAlive()
                                                fileName += msg["data"].decode()
                                                if(msg["flags"] == SYN|FIN):
                                                    fragsNums = int.from_bytes(msg["fragCount"],"big")
                                                    safePrint("prijaty ramec na zahajeneie prenosu: {} ({} fragmentov)".format(fileName,fragNums))
                                            elif msg["flags"] == FIN:
                                                try:
                                                    safePrint("Subor {} bol prijaty".format(fileName))
                                                    safePrint("ulozeny v: {}".format(self.downloadDirectory+fileName))
                                                    safePrint("počet prijatych fragmentov: {}".format(fragCount))
                                                    f = open(self.downloadDirectory+fileName, "wb")
                                                    f.write(buildFile)
                                                    f.close()
                                                    buildFile = b""
                                                    fileName = ""
                                                    poradie = 0
                                                    self.con.enableKeepAlive()
                                                except Exception:
                                                    safePrint("failed to write")
                                            else:
                                                poradie += 1
                                                fragsNums = int.from_bytes(msg["fragCount"],"big")
                                                print("bol prijaty fragment {}. z {} -- prijaty bez chyby".format(poradie,fragsNums), end="\r")
                                                buildFile += msg["data"]
                                                fragCount+=1
                                        #self.con.socket.sendto(encapsulateData(0x00,ACK+msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b""),addr)
                                    if self.con.awaitedWindow == MAX_SEQ:
                                        self.con.awaitedWindow = 0

            else:
                print("---- LISTEN THREAD END ----")
                break