
import socket
import sys
import os
import re
import pathlib

from src.connection import Connection
from src.threads import listenThread, sendThread
from src.constants import ACK, CONTROL, EMPTY, FILE, SYN, TEXT,FIN, SWAP, fragment


def simulate():
    simulate = -1
    while simulate == -1:
        simulate = input("chcete simulovat chybu (1 - ano; 0 - nie): ")
        try:
            simulate = int(simulate)
            if simulate == 0:
                simulate = False
            elif simulate == 1:
                simulate = True
            else:
                print("bad input")
                simulate = -1
        except Exception:
            print("bad input")
            simulate = -1
    return simulate

def setFragSize():
    fragSize = 0
    while fragSize == 0:
        fragSize = input("zadajte velkost fragemntu <1-565>: ")
        try:
            fragSize = int(fragSize)
            if fragSize > 565:
                print("prekrocene max pre fragemnt nastavujem na 565")
                fragSize = 565
            if fragSize < 0:
                print("velkost musi byt viac ako 0")
                fragSize = 0
        except Exception:
            print("Nezadali ste cislo")
            fragSize = 0

    return fragSize



def operations(connection : Connection, listenThread : listenThread, sendThread : sendThread):
    while True:
        print("0 - ukoncenie\n1 - poslanie textovej spravy\n2 - poslanie suboru\n3 - vymena")
        option = input()
        if option == "0":
            if connection.transferDone():
                if connection.sending != 1 and connection.getConnected() and connection.keepAliveSend == False:
                    connection.send(CONTROL,FIN,0,b"")
                    connection.end = True
                    connection.closeEvent.wait()
                    connection.closeEvent.clear()
                    connection.changeState(1,False)
                    connection.socket.close()
                    listenThread.join()
                    sendThread.join()
                else:
                    connection.changeState(1,False)
                    connection.socket.close()
                    listenThread.join()
                    sendThread.join()
                return False
            else:
                print("packets are still transmitting")
        elif option == "1": # string
            msg = ""
            if connection.sending != 1:
                if not connection.transferDone() and not connection.keepAliveSend:
                    continue;
                fragSize = setFragSize()
                while msg == "":
                    msg = input("zadajte spravu: ")

                connection.simulateMistake = simulate()
                
                frags = fragment(bytes(msg, "ascii"),fragSize)
                num = len(frags)
                print("Veľkosť správy: {}B (bude prenesenych {}B dat)".format(len(msg),fragSize*num))
                print("Rozdelena na: {} fragmentov ({}B fragment)".format(num,fragSize))
                with connection.windowCondtion:
                    connection.sending = 2
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,0,b"")
                    print("sending init frame")
                connection.disableKeepAlive()
                connection.sendMultiple(TEXT,EMPTY,num,frags)
                connection.rstTime()
                #connection.disableKeepAlive()
                del frags
            else:
                print("In listening mode")
            pass
        elif option == "2": #subor
            if connection.sending != 1:
                if not connection.transferDone() and not connection.keepAliveSend:
                    continue;
                path = ""
                fragSize = setFragSize()
                while path == "":
                    path = input("zadajte cestu k suború: ")
                try:
                    f = open(path,"rb")
                    data= f.read()
                except Exception:
                    print("Invalid File")
                    continue;

                connection.simulateMistake = simulate()
                
                frags= fragment(data,fragSize)
                num = len(frags)
                fileName = pathlib.Path(path).name
                fragName = fragment(fileName.encode("ascii"),fragSize)
                numName = len(fragName)
                print("umiestnenie súboru: {}".format(os.path.abspath(path)))
                print("nazov súboru {} bol fragmentovany na {} kusov (bude prenesenych {}B dat)".format(path,numName,fragSize*numName))
                print("veľkosť názvu: {}B".format(len(fileName)))
                print("súbor {} bol fragmentovany na {} kusov (fragment: {}B)".format(path,num,fragSize))
                print("Veľkosť suboru: {}B (bude prenesenych: {}B dat)".format(len(data),num*fragSize))
                with connection.windowCondtion:
                    connection.sending = 2
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,0,b"")
                connection.disableKeepAlive()
                connection.sendMultiple(FILE,SYN,numName,fragName)
                connection.sendMultiple(FILE,EMPTY,num,frags)
                print("added all frags to queue")
                connection.rstTime()
                del fragName
                del frags

            else:
                print("In listening mode")
        elif option == "3":
            if connection.sending != 1 and connection.connected:
                if not connection.transferDone() and not connection.keepAliveSend:
                    continue;
                connection.send(CONTROL,SWAP,0,b'');
                connection.rstTime()
                #connection.disableKeepAlive()
            else:
                print("In listening mode")

def server(port,host,download):
    print("Hostname: ",socket.gethostbyaddr(host)[0])
    print("IP addresa: ", host)
    print("port: ",port)
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.bind((host,port))
    except Exception:
        print("Couldnt create socket")
        return False;

    connection = Connection(s,True)
    connection.connected = True
    connection.sending = 1;
    serverListen = listenThread(connection,download)
    serverSendThread = sendThread(connection)

    serverListen.start()
    serverSendThread.start()
    operations(connection,serverListen,serverSendThread)

    return True


def client(port, hostIP,download):  
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    print()
    print("server to connect:",hostIP)
    print("port:",port)
    try:
        socket.getaddrinfo(hostIP,port)
    except Exception:
        print("Unreachable ip address")
        return

    connection = Connection(s)
    connection.addr = (hostIP,port)
    connection.sending = 2
    clientSend = sendThread(connection)
    clientListen = listenThread(connection,download)

    clientListen.start()
    clientSend.start()
    operations(connection,clientListen,clientSend)


if __name__ == '__main__':
    close = False
    downloadDirectory = input("zadajte cestu kam sa maju subory ukladat: ")
    while  downloadDirectory != "" and not os.path.isdir(downloadDirectory):
        downloadDirectory = input("zadajte cestu kam sa maju subory ukladat: ")
    if downloadDirectory == "":
        downloadDirectory =  "./Downloads/"
    if downloadDirectory[-1] != '/':
        downloadDirectory+= '/'
    while not close:
        #port = input("zadajte port servera: ")
        print(" 0 - quit\n 1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")
        if mode == "0":
            close = True
        elif mode == "2":
            IP = input("zadajte ip servera: ")
            while not bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",IP)):
                print(" --- Invalid ip address ---")
                IP = input("zadajte ip servera: ")
            while True:
                port ="" 
                port = input("zadajte port servera <1024-65535>: ")
                while not port.isdigit():
                    port = input("zadajte port servera <1024-65535>: ")
                port = int(port)
                if port >= 1024 and port <= 65535:
                    break;
                print("ERROR: pouzity zly port")
            print("------------ CLIENT ---------------")
            client(port,IP,downloadDirectory)
        elif mode == "1":
            print("---------- SERVER INIT -----------")
            addresses = ["127.0.0.1"]
            i = 1
            print("choose interface: ")
            print("0 -- 127.0.0.1 -- local host")
            for addr in socket.getaddrinfo(socket.gethostname(),None):
                if addr[0] == socket.AddressFamily.AF_INET:
                    addresses.append(addr[4][0])
                    print("{} -- {}".format(i,addr[4][0]))
                    i+=1
            while True:
                il = input("interface: ")
                while not il.isdigit():
                    il = input("interface: ")
                il = int(il)
                if il >= 0 and il < len(addresses):
                    host = addresses[il];
                    break;
                print("ERROR: Invalid interface")

            while True:
                port ="" 
                port = input("zadajte port servera <1024-65535>: ")
                while not port.isdigit():
                    port = input("zadajte port servera <1024-65535>: ")
                port = int(port)
                if port >= 1024 and port <= 65535:
                    break;
                print("ERROR: pouzity zly port")
            print("------------ SERVER ---------------")
            if not server(port,host, downloadDirectory):
                break;
        else:
            print("neplatna moznost")
