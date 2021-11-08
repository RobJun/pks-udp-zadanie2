import socket
import sys
import threading
from src.connection import Connection

from src.threads import serverThread

def server(port):
    hostname = socket.gethostname()
    host =  socket.gethostbyname(hostname) 
    print("Hostname: ",hostname)
    print("IP addresa: ", host)
    print("port: ",port)

    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.bind((host,port))
    except Exception:
        print("Couldnt create socket")
        sys.exit(1)
    con = Connection(s)
    threadCondition = threading.Condition() 
    server = serverThread(threadCondition,con)

    server.start()

    while True:
        input("send ping")
        con.send("fromServer".encode())
    s.close()