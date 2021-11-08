import socket

class Connection:
    def __init__(self,socket : socket.socket):
        self.socket = socket
        self.running = True
        self.fsize = 1024 
        self.addr = 0


    def recieve(self):
        msg,addr = self.socket.recvfrom(self.fsize)
        if self.addr == 0:
            self.addr = addr

        return msg,addr

    def send(self,msg : bytes):
        if(self.addr != 0):
            self.socket.sendto(msg,self.addr)