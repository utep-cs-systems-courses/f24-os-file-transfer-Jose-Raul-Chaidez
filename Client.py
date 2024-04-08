#! /usr/bin/env python3

# Echo client program
import socket, sys, re, os, time
sys.path.append("lib")       # for params
import params

switchesVarDefaults = (
    (('-s', '--server'), 'server', "127.0.0.1:50001"),
    (('-d', '--delay'), 'delay', "0"),
    (('-?', '--usage'), "usage", False), # boolean (set if present)
    )


paramMap = params.parseParams(switchesVarDefaults)

server, usage  = paramMap["server"], paramMap["usage"]

if usage:
    params.usage()

try:
    serverHost, serverPort = re.split(":", server)
    serverPort = int(serverPort)
except:
    print("Can't parse server:port from '%s'" % server)
    sys.exit(1)

s = None
for res in socket.getaddrinfo(serverHost, serverPort, socket.AF_UNSPEC, socket.SOCK_STREAM):
    af, socktype, proto, canonname, sa = res
    try:
        print("creating sock: af=%d, type=%d, proto=%d" % (af, socktype, proto))
        s = socket.socket(af, socktype, proto)
    except socket.error as msg:
        print(" error: %s" % msg)
        s = None
        continue
    try:
        print(" attempting to connect to %s" % repr(sa))
        s.connect(sa)
    except socket.error as msg:
        print(" error: %s" % msg)
        s.close()
        s = None
        continue
    break

if s is None:
    print('could not open socket')
    sys.exit(1)


class Deframer_Inband():
    
    def __init__(self,fd):
        
        self.fd = fd
        
    def readBytes(self, byteReader):
        
        temp = None
        
        bytesRead = bytearray()
        
        while(by := byteReader.readByte()) is not None:
            
            if (temp == ord('/')) and (by == ord('/')):
                
                bytesRead.append(ord('/'))
               
            elif (temp == ord('/')) and (by == ord('e')):
                break
            
            else:
                if(temp != None):
                    bytesRead.append(temp)
                
            temp = by
            
        return bytesRead


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
            nWritten = os.write(self.fd,self.buf[startIndex:endIndex])
            if nWritten == 0:
                os.write(2,f"buf.BufferedFdWriter(fd={self.fd}): flush failed\n".encode())
                sys.exit(1)
            startIndex += nWritten
        self.index = 0
    def close(self):
        self.flush()
        os.close(self.fd)


delay = float(paramMap['delay']) # delay before reading (default = 0s)
if delay != 0:
    print(f"sleeping for {delay}s")
    time.sleep(int(delay))
    print("done sleeping")

while 1:
    data = s.recv(2048)
    
    if len(data) == 1:
        break
        
    r_fd, w_fd = os.pipe()
        
    os.write(w_fd, data)

    deframer = Deframer_Inband(r_fd)
        
    byteReader = BufferedFdReader(r_fd)
        
    while True:
        name_bytes = deframer.readBytes(byteReader)
        print(name_bytes)
        if name_bytes == None:
            break
            
        filename = name_bytes.decode()
                
        ofile = os.open("new_" + filename, os.O_WRONLY | os.O_CREAT)
            
        byteWriter = BufferedFdWriter(ofile)
            
        content_bytes = deframer.readBytes(byteReader)
            
        os.write(ofile, content_bytes)     
    
print("Zero length read.  Closing")
s.close()
