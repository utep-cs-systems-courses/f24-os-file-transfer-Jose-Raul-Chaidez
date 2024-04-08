#! /usr/bin/env python3

# Echo server program

import socket, sys, re, os, time
sys.path.append("lib")       # for params
import params

switchesVarDefaults = (
    (('-l', '--listenPort') ,'listenPort', 50001),
    (('-?', '--usage'), "usage", False), # boolean (set if present)
    )


paramMap = params.parseParams(switchesVarDefaults)

listenPort = paramMap['listenPort']
listenAddr = ''       # Symbolic name meaning all available interfaces

pidAddr = {}                    # for active connections: maps pid->client addr 

if paramMap['usage']:
    params.usage()


class Framer_Outband:

    def __init__(self,fd):

        self.fd = fd
        
    def Begin(self, size, byteWriter):
        
        
        length = "00000000"
        
        size = "{:08d}".format(int(length) + size)
        
        for b in size:
            byteWriter.writeByte(ord(b))
        
        
    def Write(self, by, byteWriter, name):
        
        if(name == True):
            
            for bv in by:
                
                byteWriter.writeByte(ord(bv))
            
        else:
            while (b := by.readByte()) is not None:

                byteWriter.writeByte(b)
        
    def Close(self, byteWriter):
        
        byteWriter.flush()
        
class BufferedFdReader:
    def __init__(self, fd, bufLen = 1024*16):
        self.fd = fd
        self.buf = b""
        self.index = 0
        self.bufLen = bufLen
    def readByte(self):
        if self.index >= len(self.buf):
            self.buf = os.read(self.fd, self.bufLen)
            self.index = 0
        if len(self.buf) == 0:
            return None
        else:
            retval = self.buf[self.index]
            self.index += 1
            return retval
    def close(self):
        os.close(self.fd)

class BufferedFdWriter:
    def __init__(self, fd, bufLen = 1024*16):
        self.fd = fd
        self.buf = bytearray(bufLen)
        self.index = 0
    def writeByte(self, bVal):
        self.buf[self.index] = bVal
        self.index += 1
        if self.index >= len(self.buf):
            self.flush()
    def flush(self):
        startIndex, endIndex = 0, self.index
        while startIndex < endIndex:
            nWritten = self.fd.send(self.buf[startIndex:endIndex])
            print("file sent")
            if nWritten == 0:
                os.write(2,f"buf.BufferedFdWriter(fd={self.fd}): flush failed\n".encode())
                sys.exit(1)
            startIndex += nWritten
        self.index = 0
    def close(self):
        self.flush()
        os.close(self.fd)


# server code to be run by child
def chatWithClient(connAddr):  
    sock, addr = connAddr
    print(f'Child: pid={os.getpid()} connected to client at {addr}')
    
    
    files = ["foo.txt","goo.gif"]
        
    byteWriter = BufferedFdWriter(sock)
    
    for filename in files:
        try:
            print(filename)
            fd = os.open(filename, 0)
                
            framer = Framer_Outband(fd)
                    
            ifile = BufferedFdReader(fd)
                
            framer.Begin(len(filename), byteWriter)
            
            framer.Write(filename,byteWriter, True)
            
            file_stats = os.stat(fd)
            
            size = file_stats.st_size
        
            framer.Begin(size,byteWriter)
                        
            framer.Write(ifile,byteWriter, False)
                                    
        except FileNotFoundError:
            print(f"File '{filename}' not found.")            
    
    framer.Close(byteWriter)
    
    sock.shutdown(socket.SHUT_WR)
    print("Socket shut down")
    
    sys.exit(0)                 # terminate child

listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# listener socket will unbind immediately on close
listenSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# accept will block for no more than 5s
listenSock.settimeout(5)          
# bind listener socket to port
listenSock.bind((listenAddr, listenPort))
# set state to listen
listenSock.listen(1)              # allow only one outstanding request

# s is a factory for connected sockets


while True:
    # reap zombie children (if any)
    while pidAddr.keys():
        # Check for exited children (zombies).  If none, don't block (hang)
        if (waitResult := os.waitid(os.P_ALL, 0, os.WNOHANG | os.WEXITED)): 
            zPid, zStatus = waitResult.si_pid, waitResult.si_status
            print(f"""zombie reaped:
            \tpid={zPid}, status={zStatus}
            \twas connected to {pidAddr[zPid]}""")
            del pidAddr[zPid]
        else:
            break               # no zombies; break from loop
    print(f"Currently {len(pidAddr.keys())} clients")

    try:
        connSockAddr = listenSock.accept() # accept connection from a new client
    except TimeoutError:
        connSockAddr = None 

    if connSockAddr is None:
        continue
        
    forkResult = os.fork()     # fork child for this client 
    if (forkResult == 0):        # child
        listenSock.close()         # child doesn't need listenSock
        chatWithClient(connSockAddr)
    # parent
    sock, addr = connSockAddr
    sock.close()   # parent closes its connection to client
    pidAddr[forkResult] = addr
    print(f"spawned off child with pid = {forkResult} at addr {addr}")
