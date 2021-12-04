import socket
import sys
import os
import re
import pathlib
from src.progressBar import printProgressBar

from src.connection import Connection
from src.threads import clientListenThread, clientSendThread
from src.constants import ACK, CONTROL, EMPTY, FILE, SYN, TEXT,FIN, SWAP, fragment


def operations(connection : Connection, listenThread : clientListenThread, sendThread : clientSendThread):
    while True:
        print("0 - ukoncenie klienta\n1 - poslanie textovej spravy\n2 - poslanie suboru")
        option = input()
        if option == "0":
            if connection.transferDone():
                if not connection.server and connection.getConnected():
                    #connection.send(CONTROL,FIN,0,b"")
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
            fragSize = 0
            msg = ""
            if connection.sending != 1:

                while fragSize == 0:
                    fragSize = input("zadajte velkost fragemntu <1-X>: ")
                    try:
                        fragSize = int(fragSize)
                    except Exception:
                        fragSize = 0
                while msg == "":
                    msg = input("zadajte spravu: ")
                frags,num = fragment(bytes(msg, "ascii"),fragSize)
                print("Veľkosť správy: {}B ")
                with connection.windowCondtion:
                    connection.sending = 2
                connection.fragCount = num;
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,0,b"")
                    print("sending init frame")
                connection.disableKeepAlive()
                connection.sendMultiple(TEXT,EMPTY,num,frags,True)
                connection.rstTime()
                #connection.disableKeepAlive()
                del frags
            else:
                print("In listening mode")
            pass
        elif option == "2": #subor
            if connection.sending != 1:
                fragSize = 0
                path = ""
                while fragSize == 0:
                    fragSize = input("zadajte velkost fragemntu <1-X>: ")
                    try:
                        fragSize = int(fragSize)
                    except Exception:
                        fragSize = 0
                while path == "":
                    path = input("zadajte cestu k suború: ")
                try:
                    f = open(path,"rb")
                    data= f.read()
                except Exception:
                    print("Invalid File")
                    continue;
                frags,num = fragment(data,fragSize)
                fileName = pathlib.Path(path).name
                fragName,numName = fragment(fileName.encode("ascii"),fragSize)
                print("umiestnenie súboru: {}".format(os.path.abspath(path)))
                print("nazov súboru {} bol fragmentovany na {} kusov".format(path,numName))
                print("veľkosť názvu: {}B".format(len(fileName)))
                print("súbor {} bol fragmentovany na {} kusov".format(path,num))
                print("Veľkosť suboru: {}B".format(len(data)))
                with connection.windowCondtion:
                    connection.sending = 2
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,0,b"")
                connection.disableKeepAlive()
                connection.sendMultiple(FILE,SYN,numName,fragName,True)
                connection.sendMultiple(FILE,EMPTY,num,frags)
                connection.send(FILE,FIN,num,b"")
                print("added all frags to queue -- ready to send")
                connection.rstTime()
                del fragName
                del frags

            else:
                print("In listening mode")
        elif option == "3":
            if connection.sending != 1:
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
        sys.exit(1)

    connection = Connection(s,True)
    connection.connected = True
    connection.sending = 1;
    serverListen = clientListenThread(connection,download)
    serverSendThread = clientSendThread(connection)

    serverListen.start()
    serverSendThread.start()
    operations(connection,serverListen,serverSendThread)


def client(port, hostIP,download):  
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    print()
    print("server to connect:",hostIP)
    print("port:",port)

    connection = Connection(s)
    connection.addr = (hostIP,port)
    connection.sending = 2
    clientSend = clientSendThread(connection)
    clientListen = clientListenThread(connection,download)

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
    while not close:
        #port = input("zadajte port servera: ")
        print(" 0 - quit\n 1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")
        if mode == "0":
            close = True
        elif mode == "2":
            IP = input("zadajte ip servera: ")
            while not re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",IP):
                print(" --- Invalid ip address ---")
                IP = input("zadajte ip servera: ")
            while True:
                port ="" 
                port = input("zadajte port servera: ")
                while not port.isdigit():
                    port = input("zadajte port servera: ")
                port = int(port)
                if port > 1024 and port <= 65535:
                    break;
                print("ERROR: pouzity zly port")
            print("------------ CLIENT ---------------")
            client(port,IP,downloadDirectory)
        elif mode == "1":
            print("---------- SERVER INIT -----------")
            addresses = []
            i = 1
            print("choose interface: ")
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
                if il >= 1 and il <= len(addresses):
                    host = addresses[il-1];
                    break;
                print("ERROR: Invalid interface")

            while True:
                port ="" 
                port = input("zadajte port servera: ")
                while not port.isdigit():
                    port = input("zadajte port servera: ")
                port = int(port)
                if port > 1024 and port <= 65535:
                    break;
                print("ERROR: pouzity zly port")
            print("------------ SERVER ---------------")
            server(port,host, downloadDirectory)
        else:
            print("neplatna moznost")
