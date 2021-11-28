
#TYPES
from random import randint
import textwrap


CONTROL = 0x00
TEXT = 0x01
FILE = 0x02

#FLAGS
SYN = 0x01
FIN = 0x02
ACK = 0x04
RES = 0x08
KEEP = 0x10
SWAP = 0x20

MAX_SEQ = 65500


def simulateMistake(data : bytes):
    if randint(0,50) == 0 and len(data)-3 >9:
        index = randint(9,len(data)-3)
        nahrada = randint(0,255)
        while nahrada == data[index]:
            nahrada = randint(0,255)
        return data[:index] + int.to_bytes(nahrada,1,"big") + data[index+1:]
    return data

def fragment(data : bytes,fragSize : int) -> list:
    frags = []
    dataCopy = data[:]
    i = 1
    while len(dataCopy) > fragSize:
        c = dataCopy[:fragSize]
        frags.append((c,len(c)) )
        dataCopy = dataCopy[fragSize:]
        i+=1
    if len(dataCopy) != 0:
        f = (fragSize - len(dataCopy))
        padding = b"\0"*f
        frags.append((dataCopy + padding,len(dataCopy)))
    return frags,i

def encapsulateData(typ : int,flags : int, seqNum : int ,ackNum : int,data : bytes, lenght : int = 0):
    header = int.to_bytes(typ,1,"big")
    header += int.to_bytes(flags,1,"big")
    header += int.to_bytes(lenght,2,"big")
    header += int.to_bytes(seqNum,2,"big")
    header += int.to_bytes(ackNum,3,"big")
    if len(data) != 0:
        send = header + data
    else:
        send = header + data
    return send + int.to_bytes(calculateCRC16(send),2,"big");


def parseData(msg : bytes):
    return {"type" : msg[0], "flags" : msg[1],"size" : msg[2:4], "seqNum" : msg[4:6], "fragCount" : msg[6:9], "crc" : msg[-2:], "data" : msg[9:9+int.from_bytes(msg[2:4],'big')]}

def calculateCRC16(data : bytes):
    poly = 0x11021
    crc = 0x0000
    d = data + b"\0\0"
    for byte in d:
        byteMask = 0x80;
        for _ in range(0,8):
            xor =  crc & 0x8000 != 0
            crc <<= 1
            if byte & byteMask:
                crc+=1
            if (xor):
                crc = (crc ^ (poly)) & 0xffff
            byteMask >>= 1


    return crc & 0xffff

def checkCRC16(data: bytes):
    poly = 0x11021
    crc = 0x0000
    d = data
    for byte in d:
        byteMask = 0x80;
        for _ in range(0,8):
            xor =  crc & 0x8000 != 0
            crc <<= 1
            if byte & byteMask:
                crc+=1
            if (xor):
                crc = (crc ^ (poly)) & 0xffff
            byteMask >>= 1


    return (crc & 0xffff == 0)


def safePrint(row):
    print()
    print(row)



 
