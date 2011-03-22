# This HID code from http://code.google.com/p/pywiimote/
# I modified it to work for the LS2208 but umm can't remember what I did so do a diff - ladyada
# MIT license

#NOTE:::::: use separate events for file reading and writing, so that when you convert to a
#polling system there will be no problem.

#TODO: instead of opening a KERNEL write in the functions, allow the user to pass
# an instance with a write() method.  THis way it'll be easy to debug (just pass in a screen-printing class'
#write method) as well as making it easier to make portable.  also it potentially provides an alternative
# (using HID report writing so that people with the XP stack will be okay)

#error types
class AccessDeniedError(Exception): pass
class PathNotFoundError(Exception): pass
class UnknownHandleError(Exception): pass

from ctypes import *
import sys
import win32file
import win32con   # constants.

kernel = windll.kernel32
hid = windll.hid
setupapi = windll.setupapi

#define setupapi flags used
DIGCF_DEFAULT           = 0x00000001  # only valid with DIGCF_DEVICEINTERFACE
DIGCF_PRESENT           = 0x00000002#we care about this one
#DIGCF_ALLCLASSES        = 0x00000004
#DIGCF_PROFILE           = 0x00000008
DIGCF_DEVICEINTERFACE   = 0x00000010#and this one



#from winnt.h
#define GENERIC_READ                     (0x80000000L)
#define GENERIC_WRITE                    (0x40000000L)
#define GENERIC_EXECUTE                  (0x20000000L)
#define GENERIC_ALL                      (0x10000000L)
#define FILE_SHARE_READ                 0x00000001  
#define FILE_SHARE_WRITE                0x00000002  
#define FILE_SHARE_DELETE               0x00000004
#define FILE_FLAG_WRITE_THROUGH         0x80000000
#define FILE_FLAG_OVERLAPPED            0x40000000
#define FILE_FLAG_NO_BUFFERING          0x20000000
#define FILE_FLAG_RANDOM_ACCESS         0x10000000
#define FILE_FLAG_SEQUENTIAL_SCAN       0x08000000
#define FILE_FLAG_DELETE_ON_CLOSE       0x04000000
#define FILE_FLAG_BACKUP_SEMANTICS      0x02000000
#define FILE_FLAG_POSIX_SEMANTICS       0x01000000
#define FILE_FLAG_OPEN_REPARSE_POINT    0x00200000
#define FILE_FLAG_OPEN_NO_RECALL        0x00100000
#define FILE_FLAG_FIRST_PIPE_INSTANCE   0x00080000
#define CREATE_NEW          1
#define CREATE_ALWAYS       2
#define OPEN_EXISTING       3
#define OPEN_ALWAYS         4
#define TRUNCATE_EXISTING   5

#The ones we actually use:
GENERIC_READ = 0x80000000L
GENERIC_WRITE = 0x40000000L
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 0x000000003
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_ACCESS_DENIED = 5
ERROR_PATH_NOT_FOUND = 3

class GUID(Structure):
    _fields_ = [('Data1',c_ulong), ('Data2',c_ushort),
    ('Data3',c_ushort), ('Data4',c_ubyte*8)]
class DeviceInterfaceData(Structure):
    _fields_ = [('cbSize',c_ulong), ('InterfaceClassGuid',GUID),('Flags',c_ulong),('Reserved',POINTER(c_ulong))]

#the following classes are defined so that we can create an OVERLAPPED structure.
class struct(Structure):
    _fields_ = [("Offset",c_ulong),("OffsetHigh",c_ulong)]
class union(Union):
    _fields_ = [("",struct),("Pointer",c_void_p)]
#class OVERLAPPED(Structure):
#    _fields_ = [("Internal",POINTER(c_ulong)), ("Internal_High",POINTER(c_ulong)),("",union),("hEvent",c_void_p)]

class HidAttributes(Structure):
    _fields_ = [('Size',c_ulong),('VendorID',c_ushort),('ProductID',c_ushort),('VersionNumber',c_ushort)]

class CommTimeouts(Structure):
    _fields_ = [('ReadIntervalTimeout', c_ulong),
                ('ReadTotalTimeoutMultiplier', c_ulong),
                ('ReadTotalTimeoutConstant', c_ulong),
                ('WriteTotalTimeoutMultiplier', c_ulong),
                ('WriteTotalTimeoutConstant', c_ulong)]
def OpenDevice(index):
    guid = GUID()
    hid.HidD_GetHidGuid(byref(guid))
    setupapi.SetupDiGetClassDevsA.restype = c_void_p
    #classdevices = c_void_p(setupapi.SetupDiGetClassDevsA(byref(guid),None,None,(DIGCF_PRESENT|DIGCF_DEVICEINTERFACE)))
    classdevices = setupapi.SetupDiGetClassDevsA(byref(guid),None,None,(DIGCF_PRESENT|DIGCF_DEVICEINTERFACE))

    #setupapi.SetupDiGetClassDevsA(byref(guid),None,None,(DIGCF_PRESENT|DIGCF_DEVICEINTERFACE))

    deviceinterfacedata = DeviceInterfaceData()

    deviceinterfacedata.cbSize = sizeof(deviceinterfacedata)#16+4+4+4
    deviceinterfacedata.InterfaceClassGuid = guid
    deviceinterfacedata.Flags = 0
    deviceinterfacedata.Reserved = None

    device = setupapi.SetupDiEnumDeviceInterfaces(classdevices,None,byref(guid),index,byref(deviceinterfacedata))
    buflen = c_ulong()
    setupapi.SetupDiGetDeviceInterfaceDetailA(classdevices,byref(deviceinterfacedata),None,0,byref(buflen),0)

    class DeviceInterfaceDetailData(Structure):
        _fields_ = [('cbSize',c_ulong), ('DevicePath',c_char * (buflen.value+1))]
    device = setupapi.SetupDiEnumDeviceInterfaces(classdevices,None,byref(guid),index,byref(deviceinterfacedata))
    detail = DeviceInterfaceDetailData()
    detail.cbSize = sizeof(c_ulong)+1 # Size of cbSize itself plus size of a null string.
    setupapi.SetupDiGetDeviceInterfaceDetailA(classdevices,byref(deviceinterfacedata),byref(detail),buflen,None,None)

    if setupapi.SetupDiDestroyDeviceInfoList(classdevices):
        pass
        #return detail.DevicePath
    else:
        print "Unable to delete device list."
        raise OSError


    kernel.CreateFileA.restype = c_void_p
    handle = kernel.CreateFileA(detail.DevicePath,GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                            OPEN_EXISTING, None, None)
    #print kernel.GetLastError()
    if handle == -1:
        error = kernel.GetLastError()
        print error
        if error == ERROR_ACCESS_DENIED:
            raise AccessDeniedError
        elif error == ERROR_PATH_NOT_FOUND:
            raise PathNotFoundError
        else:
            raise UnknownHandleError# we should give people some way of accessing the error code in this case.
        
        kernel.CloseHandle(handle)
        #return error
        
    return handle

def OpenDevices(vendorid=None,productid=None):
    """opens all hid devices currently on the system (That we have access to,)
    connects to all of them, and disconnects and removes them from the list if their vendorid and productid
    don't match the parameters.  If the parameters' default values of None remain, the list will be returned
    in its entirety with all devices connected (read the HID attributes already, so devicelist[0].vendorid can
    be used to check the first returned item's vendor id, for example.)
    refer to HIDDevice.connect for pitfalls."""
    x = 0
    devices = []
    end = False
    while not end:
        try:
            handle = OpenDevice(x)
            temp = HIDDevice(handle)
            #print temp.vendorid
            #if (temp.vendorid == 0) and (temp.productid == 0):
            #   break
            if temp.vendorid in [vendorid, None] and temp.productid in [productid, None]:
                
                devices.append(temp)
            else: #disconnect from them, just to be sure we don't leak anything.
                temp.disconnect()
            
            
        except AccessDeniedError:
            pass
        except PathNotFoundError:
            #if we're here we've run out of valid paths
            #so it's time to exit.
            end = True
        x += 1
        if (x == 100):
          end = True
        #don't catch UnknownHandleError.
    return devices
        

class HIDDevice(object):
    
    def __init__(self, handle):
        self.handle = handle
        self.connected = False
        self.connect()
        
    def connect(self):
        """precondition: self.handle is pointing to a valid device.
           postcondition: self.vendorid, self.productid, self.version set.
           success of call to connect does not mean that a device is active.
           vendor, product and version are all available whether the device
           is active or not."""
        
        attrib = HidAttributes()
        attrib.Size = sizeof(attrib)
        hid.HidD_GetAttributes(self.handle,byref(attrib))
        self.vendorid = attrib.VendorID
        self.productid = attrib.ProductID
        self.version = attrib.VersionNumber
        self.connected = True
        #print "|VendorID: %s, Product ID: %s, Version: %s" % (attrib.VendorID, attrib.ProductID, attrib.VersionNumber)

    
    def disconnect(self):
        if self.connected:
            if kernel.CloseHandle(self.handle):# and kernel.CloseHandleA(self.event):
                self.connected = False
                return True
            return False
        return True
    def __del__(self):
        """automatically disconnect, just to make sure we don't leave
        a file handle open."""
        self.disconnect()
    
    def write(self, data, length=22):
        """ data should be a list of numbers between 0 and 255 (no checking occurs at the moment).
        returns True if the write succeeded, and False if it didn't."""
        temp = c_ubyte * (length)
        temp = temp()
        print "DATA IS: ",data
        length = min(len(data), length)
        # we ignore the first value.  this is not the case if using hidD.setOutputReport.
        for x in range( length-1 ):
            #print data[x]
            temp[x] = data[x+1]
        #print temp
        #temp[x+1] = 0
        #print type(temp)
        #print temp
        #temp.value = data
        #result = hid.HidD_SetOutputReport(handle, byref(temp), c_int(len(data)-1))
        bytes_written = c_int(-1)
        #result = hid.HidD_SetOutputReport(handle,byref((c_byte * 3)(0x12,0x00,0x31)),c_int(3))
        result = kernel.WriteFile(self.handle,byref(temp),c_int(22),byref(bytes_written),None)

        #print kernel.GetLastError()
        #print "%s bytes written. " % bytes_written
        #print "result: " + str(result)
        if result: return True
        return False

    def read(self,bufsize=0x16):
        temp = c_ubyte * bufsize
        temp = temp()
        bytes_read = c_int(-1)
        bytes_avail = c_ulong(0)
        bytes_left = c_int(-1)

        to = CommTimeouts(10, 20, 30, 40, 50)
        to.cbSize = 40

        #to.ReadIntervalTimeout = 1
        #to.ReadTotalTimeoutMultiplier = 2
        #to.ReadTotalTimeoutConstant = 3
        #to.WriteTotatTimeoutMultiplier = 4
        #to.WriteTotatTimeoutConstant = 5
        #print to.cbSize
        #print to.ReadIntervalTimeout,
        #print to.ReadTotalTimeoutMultiplier,
        #print to.ReadTotalTimeoutConstant,
        #print to.WriteTotalTimeoutMultiplier,
        #print to.WriteTotalTimeoutConstant,
        #print("timeouts? "),
        #print kernel.SetCommTimeouts(self.handle, byref(to)),
        #print kernel.GetCommTimeouts(self.handle, byref(to))
        #print to.ReadIntervalTimeout,
        #print to.ReadTotalTimeoutMultiplier,
        #print to.ReadTotalTimeoutConstant,
        #print to.WriteTotalTimeoutMultiplier,
        #print to.WriteTotalTimeoutConstant,


        #print("peeking...")
        #print kernel.PeekNamedPipe(self.handle, None, 0, None, byref(bytes_avail), None)
        #print "lasterror: ", kernel.GetLastError()
        #print bytes_avail
        #if (bytes_avail.value == 0):
        #    return (0, None)
       # 
        #print("reading...")
        kernel.ReadFile(self.handle, byref(temp),bufsize,byref(bytes_read),None)
        #print "lasterror: ", kernel.GetLastError()
        #print("read")
        #print x
        #print bytes_read
        #result = kernel.WaitForSingleObject(overlapped.hEvent, timeout)
        #print overlapped
        #if result == 0:#WAIT_OBJECT_0 which is STATUS_WAIT_0 (which is 0) + 0
        #    kernel.ResetEvent(overlapped.hEvent)
        return bytes_read.value, temp
        #print "Read Timed Out"
        #something unexpected happened (implicit else)
        #kernel.CancelIo(handle)
        #kernel.ResetEvent(overlapped.hEvent)
#x = OpenDevices(0x057e,0x0306)
#print x[0].read()
#print x[1].read()
#x[0].write([0x52,0x12, 0x00, 0x30])
#x[1].write([0x52,0x12, 0x00, 0x30])
#while True:
#    print x[1].read()
#print x[0].vendorid
#def OpenAllDevices(
