import socket


def client(port):
    host = input("Zadajte ip adresu servera: ")
    
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    print()
    print("server to connect:",host)
    print("port:",port)
    while True:
        msg = input("Message to send: ")

        s.sendto(msg.encode(),(host,port))
        d = s.recvfrom(1024)
        

        print("Server:",d[0].decode())