
import threading
import time
import os
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
                if self.con.keepAliveSend:
                    if (self.con.keepAliveFirstFrame or self.con.checkKeepAliveTimer(False,5)) and not self.con.waitingForKeepAck:
                        self.con.send(CONTROL,KEEP,0,b'')
                        self.con.rstTime()
                        self.con.rstTimeAliveClock(False)
                        self.con.keepAliveFirstFrame = False;
                        self.con.waitingForKeepAck = True;
                        safePrint("-> sending keep alive")
                elif self.con.keepAliveAwait and self.con.checkKeepAliveTimer(True,10):
                    self.con.keepAlive = False;
                    self.con.flushConnection()
                    safePrint("{} didnt recieve keep alive in time -- ending connection".format("server" if self.con.server else "client"))

                if self.con.canSend() or self.con.keepAliveSend:
                    if not self.con.transferDone():
                        self.con.sendNext()
                        #print("sending {} frame".format(self.con.getCurrentWindowSize()-1))
                        if self.con.checkTime():
                            if self.con.resendWindow(True):
                                safePrint("-> timeout -- resending window")
                                self.con.rstTime()
            else:
                print("---- SENDING THREAD END ----")
                break

class clientListenThread(threading.Thread):
    def __init__(self,connection : Connection, downloadDirectory = "./Downloads/"):
        threading.Thread.__init__(self)
        self.con = connection
        self.downloadDirectory = downloadDirectory

    def run(self):
        print("---- LISTEN THREAD START ----")
        buildText = []
        fileName =""
        fragCount = 0
        poradie = 0
        while True:
            if self.con.getRunning():
                recv = self.con.recieve()
                if recv != None:
                    correct,msg, addr = recv
                    msg = parseData(msg)
                    if (msg["flags"] & ACK and correct):
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
                                    safePrint("<- server keep alive accepted")
                                    self.con.waitingForKeepAck = False;
                                    self.con.rstTime()
                                elif msg["type"] == CONTROL and msg["flags"] == SWAP | ACK:
                                    safePrint("<- other side accepted swap")
                                    self.con.sending = 1
                                    self.con.awaitedWindow = 0
                                    self.con.flushConnection(False)
                                elif self.con.transferDone() and not self.con.keepAliveSend:
                                    self.con.enableKeepAliveSend()
                    else:
                        if addr == self.con.addr or (self.con.addr == 0 and msg["type"] == CONTROL and msg["flags"] == SYN):
                            if not correct:
                                self.con.socket.sendto(encapsulateData(CONTROL,ACK|RES,int.from_bytes(msg["seqNum"],"big"),0,b""),addr)
                                safePrint("Bol prijaty chybny ramec -- posielam NACK")
                            elif recv[0] == b'':
                                pass;
                            else:
                                seq = int.from_bytes(msg["seqNum"],"big")
                                print("bol prijaty ramec {} -- {} ({})".format(msg["flags"],seq,self.con.awaitedWindow))
                                if ((seq < self.con.awaitedWindow and seq >= self.con.windowSize)
                                 or ( self.con.awaitedWindow < self.con.maxWindowSize and seq >= MAX_SEQ - (self.con.maxWindowSize - self.con.awaitedWindow))):
                                    if msg["type"] == CONTROL:
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        try:
                                            self.con.socket.sendto(reply,addr)
                                        except Exception:
                                            print("Couldnt send reply")
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        try:
                                            self.con.socket.sendto(reply,addr)
                                        except Exception:
                                            print("Couldnt send reply")
                                elif seq == self.con.awaitedWindow:
                                    self.con.awaitedWindow += 1
                                    if msg["type"] == CONTROL:
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        try:
                                            self.con.socket.sendto(reply,addr)
                                        except Exception:
                                            print("Couldnt send reply")
                                        if msg["flags"] == SWAP:
                                            self.con.sending = 2;
                                            self.con.flushConnection(False)
                                            self.con.awaitedWindow = 0
                                            print("Client disconnected")
                                            safePrint("you can now send files to: {}".format(addr[0]))
                                        elif msg["flags"] == SYN:
                                            self.con.addr = addr
                                            self.con.changeState(0,True)
                                            safePrint("Connection started with {}".format(addr[0]))
                                        elif msg["flags"] == FIN:
                                            self.con.awaitedWindow = 0
                                            self.con.addr = 0
                                            self.con.flushConnection()
                                            safePrint("Connection terminated with {}".format(addr[0]))
                                        elif msg["flags"] == KEEP:
                                            safePrint("Connection kept-alive with {}".format(addr[0]))
                                            self.con.rstTimeAliveClock(True)
                                            pass #reset timer
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        try:
                                            self.con.socket.sendto(reply,addr)
                                        except Exception:
                                            print("Couldnt send reply")
                                        if msg["type"] == TEXT:
                                            self.con.disableKeepAlive()
                                            fragsNums = int.from_bytes(msg["fragCount"],"big")
                                            if fragCount == 0:
                                                print("idem prijať {} fragmentov pre textovu spravu".format(fragsNums))
                                                fragCount = fragsNums
                                                buildText = [0]*fragCount
                                                continue;
                                            buildText[fragsNums-1] = msg["data"]
                                            poradie += 1
                                            lenght = int.from_bytes(msg["size"],"big")
                                            print("bol prijaty fragment {}. z {}  ({}B)-- prijaty bez chyby".format(fragCount,fragCount,lenght))
                                            if msg["flags"] == FIN:
                                                text = ""
                                                for i in buildText:
                                                    text+= i.decode()
                                                print("Pocet fragmentov: ", fragCount)
                                                print("Veľkosť: {}B".format(len(text)))
                                                print("!!Prijata sprava:  ",text)
                                                buildText = []
                                                poradie = 0
                                                fragCount = 0
                                                self.con.enableKeepAliveAwait()
                                        elif msg["type"] == FILE:
                                            if msg["flags"] & SYN:
                                                self.con.disableKeepAlive()
                                                fragsNums = int.from_bytes(msg["fragCount"],"big")
                                                if fragCount == 0:
                                                    print("idem prijať {} fragmentov pre nazov suboru".format(fragsNums))
                                                    fragCount = fragsNums
                                                    buildText = [0]*fragCount
                                                    continue;
                                                buildText[fragsNums-1] = msg["data"]
                                                poradie += 1
                                                lenght = int.from_bytes(msg["size"],"big")
                                                print("bol prijaty fragment {}. z {} ({}B) -- prijaty bez chyby ".format(fragsNums,fragCount,lenght))
                                                if(msg["flags"] == SYN|FIN):
                                                    print("zahajeneie prenosu: {} ({} fragmentov - {}B)".format(fileName,fragsNums,len(fileName)))
                                                    print()
                                                    for i in buildText:
                                                        fileName += i.decode()
                                                    fragCount = 0
                                                    buildText = []
                                            elif msg["flags"] == FIN:
                                                try:
                                                    buildFile = b""
                                                    for i in buildText:
                                                        buildFile += i
                                                    print("Subor {} bol prijaty".format(fileName))
                                                    print("ulozeny v: {}".format(os.path.abspath(self.downloadDirectory+fileName)))
                                                    print("počet prijatych fragmentov: {}".format(fragCount))
                                                    print("Velkosť: {}B".format(len(buildFile)))
                                                    f = open(self.downloadDirectory+fileName, "wb")
                                                    f.write(buildFile)
                                                    f.close()
                                                except Exception:
                                                    safePrint("failed to write")
                                                buildText = []
                                                fileName = ""
                                                fragCount = 0
                                                self.con.enableKeepAliveAwait()

                                            else:
                                                fragsNums = int.from_bytes(msg["fragCount"],"big")
                                                lenght = int.from_bytes(msg["size"],"big")
                                                if fragCount == 0:
                                                    fragCount = fragsNums
                                                    buildText = [0]*fragCount
                                                    print("idem prijať {} fragmentov pre data suboru".format(fragsNums))
                                                    continue;
                                                poradie += 1
                                                print("bol prijaty fragment {}. z {} ({}B) -- prijaty bez chyby".format(fragsNums,fragCount, lenght ))
                                                buildText[fragsNums-1] = msg["data"]
                                    if self.con.awaitedWindow == MAX_SEQ:
                                        self.con.awaitedWindow = 0

            else:
                print("---- LISTEN THREAD END ----")
                break