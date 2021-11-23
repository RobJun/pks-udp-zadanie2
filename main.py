import socket
import sys
import threading
import pathlib
from src.progressBar import printProgressBar

from src.connection import Connection
from src.threads import clientListenThread, clientSendThread
from src.constants import ACK, CONTROL, FILE, SYN, TEXT,FIN, SWAP, fragment


PORT = 33821
IP = "192.168.1.2"


def operations(connection : Connection, listenThread : clientListenThread, sendThread : clientSendThread):
    while True:
        option = input()
        if option == "0":
            if connection.transferDone():
                connection.changeState(1,False)
                connection.send(CONTROL,FIN,None,None,b"")
                listenThread.join()
                sendThread.join()
                connection.socket.close()
                return False
            else:
                print("packets are still transmitting")
        elif option == "1": # string
            fragSize = ""
            msg = ""
            if connection.sending != 1:
                while msg == "":
                    fragSize = int(input("zadajte velkost fragemntu <1-X>: "))
                    msg = input("zadajte spravu: ")

                frags,num = fragment(bytes(msg, "ascii"),fragSize)
                #flag = ACK if num == 1 else ACK+FRAG
                flag = 0x00
                with connection.windowCondtion:
                    connection.sending = 2
                    connection.fragCount = num;
                    if not connection.getConnected():
                        connection.send(CONTROL,SYN,None,None,b"")
                        connection.initPacket = True
                    for frag in frags:
                        connection.send(TEXT,flag,None,None,frag)
                    connection.send(TEXT,FIN,None,None,b"")
                    connection.rstTime()
            else:
                print("In listening mode")
            pass
        elif option == "2": #subor
            if connection.sending != 1:
                fragSize = ""
                path = ""
                while path == "":
                    fragSize = int(input("zadajte velkost fragemntu <1-X>: "))
                    path = input("zadajte cestu k suború: ")
                try:
                    f = open(path,"rb")
                    data= f.read()
                    frags,num = fragment(data,fragSize)
                    print("súbor {} bol fragmentovany na {} kusov".format(path,num))
                    with connection.windowCondtion:
                        connection.sending = 2
                        if not connection.getConnected():
                            connection.send(CONTROL,SYN,None,None,b"")
                            connection.initPacket = True
                        connection.send(FILE,SYN,None,None,bytes(pathlib.Path(path).name,"ascii"))
                        #flag = ACK if num == 1 else ACK+FRAG
                        flag = 0x00
                        for frag in frags:
                            connection.send(FILE,flag,None,None,frag)
                        connection.send(FILE,FIN,None,None,b"")
                        print("ready to send")
                        printProgressBar(0,connection.fragCount,"Frag sent","Complete")
                        connection.rstTime()
                except Exception:
                    print("Invalid File")
            else:
                print("In listening mode")
        elif option == "3":
            if connection.sending != 1:
                connection.send(CONTROL,SWAP,None,None,b'');
                connection.rstTime()
            else:
                print("In listening mode")

def server(port,host):
    hostname = socket.gethostname()
    print("Hostname: ",hostname)
    print("IP addresa: ", host)
    print("port: ",port)

    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.bind((host,port))
    except Exception:
        print("Couldnt create socket")
        sys.exit(1)

    connection = Connection(s)
    connection.connected = True
    connection.sending = 1;
    serverListen = clientListenThread(connection)
    serverSendThread = clientSendThread(connection)

    serverListen.start()
    serverSendThread.start()
    operations(connection,serverListen,serverSendThread)


def client(port, hostIP):  
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    print()
    print("server to connect:",hostIP)
    print("port:",port)

    connection = Connection(s)
    connection.addr = (hostIP,port)
    connection.sending = 2
    clientSend = clientSendThread(connection)
    clientListen = clientListenThread(connection)

    clientListen.start()
    clientSend.start()
    operations(connection,clientListen,clientSend)


if __name__ == '__main__':
    close = False
    swap = False
    while not close:
        port = input("zadajte port servera: ")
        print(" 0 - quit\n 1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")
        if mode == "0":
            close = True
        elif mode == "1":
            #IP = input("zadajte ip servera")
            #port = input("zadajte port servera")
            #downloadTo = ("zadajte miesto kam sa budu ukladat subory")
            swap = server(PORT,IP)
        elif mode == "2":
            if not swap:
                pass
                #port = input("zadajte port servera")
            swap = client(PORT,IP)
