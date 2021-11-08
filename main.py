import socket

from src.client import client
from src.server import server

if __name__ == '__main__':
    close = False
    while not close:
        print("0 - quit\n1 - server\n 2 - klient")
        mode = input("Zadajte moznost: ")

        if mode == "0":
            close = True
        elif mode == "1":
            server()
        elif mode == "2":
            client()
