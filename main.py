import socket
import sys
import threading
import re
import pathlib
from src.progressBar import printProgressBar

from src.connection import Connection
from src.threads import clientListenThread, clientSendThread
from src.constants import ACK, CONTROL, FILE, SYN, TEXT,FIN, SWAP, fragment


PORT = 33821
IP = "192.168.1.2"

#Z:\5_semester\7_seminar_STU_-_priklady.pdf

def operations(connection : Connection, listenThread : clientListenThread, sendThread : clientSendThread):
    while True:
        option = input()
        if option == "0":
            if connection.transferDone():
                connection.changeState(1,False)
                #connection.send(CONTROL,FIN,None,None,b"")
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
                #flag = ACK if num == 1 else ACK+FRAG
                flag = 0x00
                with connection.windowCondtion:
                    connection.sending = 2
                connection.fragCount = num;
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,None,0,b"")
                    print("sending init frame")
                connection.sendMultiple(TEXT,0x00,0,frags,True)
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
                print("nazov súboru {} bol fragmentovany na {} kusov".format(path,numName))
                print("súbor {} bol fragmentovany na {} kusov".format(path,num))
                with connection.windowCondtion:
                    connection.sending = 2
                if not connection.getConnected():
                    with connection.windowCondtion:
                        connection.initPacket = True
                    connection.send(CONTROL,SYN,None,0,b"")
                connection.sendMultiple(FILE,SYN,numName,fragName,True)
                connection.sendMultiple(FILE,0x00,num,frags)
                connection.send(FILE,FIN,None,num,b"")
                print("ready to send")
                printProgressBar(0,connection.fragCount,"Frag sent","Complete")
                connection.rstTime()
                #connection.disableKeepAlive()
                del fragName
                del frags

            else:
                print("In listening mode")
        elif option == "3":
            if connection.sending != 1:
                connection.send(CONTROL,SWAP,None,0,b'');
                connection.rstTime()
                #connection.disableKeepAlive()
            else:
                print("In listening mode")

def server(port,host,download):
    hostname = socket.gethostname()
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
            #downloadTo = ("zadajte miesto kam sa budu ukladat subory")
            client(port,IP,downloadDirectory)
        elif mode == "1":
            while True:
                port ="" 
                port = input("zadajte port servera: ")
                while not port.isdigit():
                    port = input("zadajte port servera: ")
                port = int(port)
                if port > 1024 and port <= 65535:
                    break;
                print("ERROR: pouzity zly port")
            server(port,IP, downloadDirectory)
        else:
            print("neplatna moznost")
