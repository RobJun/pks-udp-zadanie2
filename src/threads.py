import threading
import time
from src.constants import ACK, CONTROL, FILE, KEEP, RES, TEXT,FIN,SYN,MAX_SEQ,SWAP, encapsulateData, parseData

from src.connection import Connection
from src.progressBar import printProgressBar


class keepAliveThread(threading.Thread):
    def __init__(self,keepAliveEvent : threading.Event):
        self.time = time.time()
        self.stop = False
        self.condition = threading.RLock()
        self.timeout = False
        self.event = keepAliveEvent
    
    def run(self):
        while not self.stop:
            with self.condition:
                if time.time() - self.time >= 10:
                    self.timeout = True
                    self.event.set()


class clientSendThread(threading.Thread):
    def __init__(self,connection : Connection):
        threading.Thread.__init__(self)
        self.con = connection
    
    def run(self):
        print("---- SENDING THREAD START----")
        while True:
            if self.con.getRunning():
                if self.con.canSend():
                    if not self.con.transferDone():
                        self.con.sendNext()
                        #print("sending {} frame".format(self.con.getCurrentWindowSize()-1))
                        if self.con.checkTime():
                            if self.con.resendWindow(True):
                                print("-> timeout -- resending window")
                                self.con.rstTime()
                    else:
                        pass
            else:
                print("---- SENDING THREAD END----")
                break

class clientListenThread(threading.Thread):
    def __init__(self,connection : Connection, downloadDirectory = "./"):
        threading.Thread.__init__(self)
        self.con = connection
        self.downloadDirectory = downloadDirectory

    def run(self):
        print("---- LISTEN THREAD START----")
        awaitedWindow = 0
        fileName =""
        buildFile = b""
        fragCount = 0;
        fragNums = 0;
        buildText = ""
        transferInit = 0
        while True:
            if self.con.getRunning():
                recv = self.con.recieve()
                if recv != None:
                    correct,msg, addr = recv
                    msg = parseData(msg)
                    if self.con.sending == 2 and msg["flags"] & ACK and correct:
                        if msg["flags"] == ACK | RES:
                            
                            print("-> NACK recieved -- resending window\n")
                            self.con.resendWindow(False)
                            self.con.rstTime()
                        else:
                            if self.con.ack(int.from_bytes(msg["seqNum"],"big")):
                                 printProgressBar(self.con.getCurrentFrags()+1, self.con.fragCount, prefix = 'Frag sent:', suffix = 'Complete')
                                 if msg["type"] == CONTROL and  msg["flags"] == KEEP | ACK:
                                     print("server keep alive accepted")
                                 elif msg["type"] == CONTROL and msg["flags"] == SWAP | ACK:
                                     print("other side accepted swap")
                                     self.con.sending = 1
                    else:
                        if addr == self.con.addr or (self.con.addr == 0 and msg["type"] == CONTROL and msg["flags"] == SYN):
                            if not correct:
                                self.con.socket.sendto(encapsulateData(CONTROL,ACK|RES,int.from_bytes(msg["seqNum"],"big"),0,b""),addr)
                                print("Bol prijaty chybny ramec -- posielam NACK")
                            elif recv[0] == b'':
                                pass;
                            else:
                                seq = int.from_bytes(msg["seqNum"],"big")
                                fragCount = int.from_bytes(msg["seqNum"],"big")
                                if seq < awaitedWindow:
                                    if msg["type"] == CONTROL:
                                        if ACK+msg["flags"] > 0x30:
                                            print(msg)
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                elif seq == awaitedWindow:
                                    awaitedWindow += 1
                                    if msg["type"] == CONTROL:
                                        if ACK+msg["flags"] > 0x30:
                                            print(msg)
                                        reply = encapsulateData(CONTROL,ACK | msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                        if msg["flags"] == SWAP:
                                            self.con.sending = 2;
                                            print("you can now send files to: {}".format(addr[0]))
                                        elif msg["flags"] == SYN:
                                            self.con.addr = addr
                                            print("Connection started with {}".format(addr[0]))
                                        elif msg["flags"] == FIN:
                                            awaitedWindow = 0
                                            self.con.addr = 0
                                            print("Connection terminated with {}".format(addr[0]))
                                        elif msg["flags"] == KEEP:
                                            print("Connection kept-alive with {}".format(addr[0]))
                                            pass #reset timer
                                    else:
                                        reply = encapsulateData(CONTROL,ACK,int.from_bytes(msg["seqNum"],"big"),0,b"")
                                        self.con.lastSendFrame = reply
                                        self.con.socket.sendto(reply,addr)
                                        if msg["type"] == TEXT:
                                            buildText += msg["data"].decode()
                                            if msg["flags"] == FIN:
                                                print(buildText)
                                                buildText = ""
                                        elif msg["type"] == FILE:
                                            if msg["flags"] == SYN:
                                                transferInit = seq
                                                fileName = msg["data"].decode()
                                                fragsNums = int.from_bytes(msg["fragCount"],"big")
                                                print("prijaty ramec na zahajeneie prenosu: {} ({} fragmentov)".format(fileName,fragNums))
                                            elif msg["flags"] == FIN:
                                                try:
                                                    print("Subor {} bol prijaty".format(fileName))
                                                    print("ulozeny v: {}".format(self.downloadDirectory+fileName))
                                                    print("počet prijatych fragmentov: {}".format(fragCount))
                                                    f = open(self.downloadDirectory+fileName, "wb")
                                                    f.write(buildFile)
                                                    f.close()
                                                    buildFile = b""
                                                except Exception:
                                                    print("failed to write")
                                            else:
                                                poradie = seq - transferInit
                                                print("bol prijaty fragment {}. z {} -- prijaty bez chyby".format(poradie,), end="\r")
                                                buildFile += msg["data"]
                                                fragCount+=1
                                        #self.con.socket.sendto(encapsulateData(0x00,ACK+msg["flags"],int.from_bytes(msg["seqNum"],"big"),0,b""),addr)
                                    if awaitedWindow == MAX_SEQ:
                                        awaitedWindow = 0

            else:
                print("---- CLIENT LISTEN THREAD END----")
                break