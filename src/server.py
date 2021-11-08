import socket


def server():
    port = 33821
    host =  socket.gethostname()
    print("ip addresa: ", host)
    print("port: ",port)

    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    s.bind((host,port))



    while True:
        d = s.recvfrom(1024)
        print(d)

        if not d[0]:
            break
    
        reply = "OK..."

        s.sendto(reply,d[1])
        print(d[1][0],": ", d[0])

    s.close()