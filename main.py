import socket
from src.client import client
from src.server import server


PORT = 33821

if __name__ == '__main__':
    close = False
    while not close:
        print("0 - quit\n1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")

        port = input("Zadajte port: ")
        if port.isdigit():
            port = int(port)
        else:
            port = 0
        while port < 1024 or port > 50000:
            print("neplatny port")
            portIn = input("Zadajte port: ")
            if portIn.isdigit():
                port = int(portIn)
        if mode == "0":
            close = True
        elif mode == "1":
            server(port)
        elif mode == "2":
            client(port)
