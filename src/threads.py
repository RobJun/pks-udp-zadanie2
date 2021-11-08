import threading

from src.connection import Connection



class serverThread(threading.Thread):
    def __init__(self,conditions : threading.Condition,connection : Connection):
        threading.Thread.__init__(self)
        self.cond = conditions
        self.con = connection

    def run(self):
        print("---- SERVER THREAD START----")
        print("Waiting for connection")
        while True:
            self.cond.acquire()
            if self.con.running:
        
                msg = self.con.recieve()

                print(msg)

                self.con.send("Ok...".encode())



                self.cond.notify_all()
            else:
                self.cond.wait()
            self.cond.release()


class clientThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)