import socket
import sys
import threading
import pathlib

from typing import Sequence
from src.connection import Connection
from src.threads import clientListenThread, clientSendThread,serverThread
from src.constants import ACK, CONTROL, FILE, SYN, TEXT,FIN, calculateCRC16, checkCRC16, fragment


PORT = 33821
IP = "192.168.1.2"


from src.threads import serverThread

def server(port,host,fragSize):
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
    serverListen = serverThread(connection)

    serverListen.start()

    while True:
        option = input()
        if option == "0":
            connection.changeState(1,False)
            serverListen.join()
            s.close()
            return


def client(port, hostIP,fragSize):  
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    print()
    print("server to connect:",hostIP)
    print("port:",port)

    connection = Connection(s)
    connection.addr = (hostIP,port)
    clientSend = clientSendThread(connection)
    clientListen = clientListenThread(connection)

    clientListen.start()
    clientSend.start()
    while True:
        option = input()
        if option == "0":
            connection.changeState(1,False)
            connection.send(CONTROL,FIN,None,None,b"")
            clientListen.join()
            s.close()
            return
        elif option == "1": # string
            msg = ""
            while msg == "":
                msg = input("zadajte spravu: ")
            
            frags,num = fragment(bytes(msg, "ascii"),fragSize)
            if not connection.getConnected():
                connection.send(CONTROL,SYN,None,None,b"")
            for frag in frags:
                connection.send(TEXT,ACK,None,None,frag)
            connection.send(TEXT,FIN,None,None,b"")

            pass
        elif option == "2": #subor
            path = ""
            while path == "":
                path = input("zadajte cestu k suború: ")
            f = open(path,"rb")

            frags = fragment(f.read(),fragSize)
            if not connection.getConnected():
                connection.send(CONTROL,SYN,None,None,b"")
            connection.send(FILE,SYN,None,None,)
            for frag in frags:
                connection.send(FILE,ACK,None,None,frag)
            connection.send(FILE,FIN,None,None,b"")


if __name__ == '__main__':
    close = False
    while not close:
        #fragSize = input("velkost fragmentov: ")
        #port = input("zadajte port servera")
        path = pathlib.Path("C:\\5_semester\\haha.py")
        print(path.stem);
        print(" 0 - quit\n 1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")
        if mode == "0":
            close = True
        elif mode == "1":
            #IP = input("zadajte ip servera")
            #port = input("zadajte port servera")
            #downloadTo = ("zadajte miesto kam sa budu ukladat subory")
            server(PORT,IP,3)
        elif mode == "2":
            #port = input("zadajte port servera")
            client(PORT,IP,3)
