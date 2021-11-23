
#TYPES
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

MAX_SEQ = 65000

def fragment(data : bytearray,fragSize : int) -> list:
    frags = []
    dataCopy = data[:]
    i = 1
    while len(dataCopy) > fragSize:
        frags.append(dataCopy[:fragSize])
        dataCopy = dataCopy[fragSize:]
        i+=1
    if len(dataCopy) != 0:
        frags.append(dataCopy)
    return (frags,i)

def encapsulateData(typ : int,flags : int, seqNum : int ,ackNum : int,data : bytes):
    header = int.to_bytes(typ,1,"big")
    header += int.to_bytes(flags,1,"big")
    header += int.to_bytes(len(data),2,"big")
    header += int.to_bytes(seqNum,2,"big")
    header += int.to_bytes(ackNum,2,"big")
    
    send = header + data
    return send + int.to_bytes(calculateCRC16(send),2,"big");


def parseData(msg : bytes):
    return {"type" : msg[0], "flags" : msg[1],"size" : msg[2:4], "seqNum" : msg[4:6], "fragCount" : msg[6:8], "crc" : msg[-2:], "data" : msg[8:-2]}

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

 
