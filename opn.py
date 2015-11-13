#!/usr/bin/env python

"""opn.py: Python implementation of a reader for the OPN-2001 barcode scanner

    Some documentation for the official SDK is available here:
        http://wiki.opticon.com/index.php/OPN_2001
"""

__author__ = "Simon Jouet"

import serial
import datetime
import struct

class InvalidFrameException(Exception):
    pass

crc_map = [0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241, 0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440, 0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40, 0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841, 0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40, 0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41, 0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641, 0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040, 0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240, 0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441, 0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41, 0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840, 0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41, 0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40, 0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640, 0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041, 0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240, 0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441, 0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41, 0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840, 0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41, 0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40, 0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640, 0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041, 0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241, 0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440, 0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40, 0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841, 0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40, 0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41, 0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641, 0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040]
def calculate_crc(data):
    crc_value = 0xffff

    if isinstance(data, str):
        data = bytearray(data)

    for byte in data:
        tmp = (crc_value & 0xff) ^ byte
        crc_value = ((crc_value >> 8) & 0xff) ^ crc_map[tmp]

    return ~crc_value & 0xffff


def timestampToDate(value):
    """
        4 bytes to represent when the barcode was scanned.

        31   25    19     14     9       5      0
        | sec | min | hour | day | month | year |
    """

    year   = (value & 0x3F) + 2000 # The year is only the last two digits, need to add 2000
    month  = (value >> 6) & 0x0F
    day    = (value >> 10) & 0x1F
    hour   = (value >> 15) & 0x1F
    minute = (value >> 20) & 0x3F
    second = (value >> 26) & 0x3F

    return datetime.datetime(year, month, day, hour, minute, second)

def dateToTimestamp(date):
    """
        Transform a date into the format required by the barcode reader

        3 bytes headers unknown: 09 02 06
        6 bytes each byte  a component of the datetime [sec min hour day month year]
        3 final bytes 00 34 83
    """

    return struct.pack('>BBBBBB',
        date.second,
        date.minute,
        date.hour,
        date.day,
        date.month,
        date.year - 2000
    )

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

SymbologyParameters = enum(
    CODE39 = 0x1f, # 1=Enable, 0=Disable, default = enabled
    UPC = 0x09, # 1=Enable, 0=Disable, default = enabled
    CODE_128 = 0x08, # 1=Enable, 0=Disable, default = enabled
    CODE39_ASCII = 0x36, # 1=Enable, 0=Disable, default = disable
    UPC_SUPPS = 0x35, # 0=No supps, 1=Supps only, 2=auto-d, default=auto-d
    CONVERT_UPCE_TO_UPCA = 0x29, # 1=Enable, 0=Disable, default = disabled
    CONVERT_EAN8_TO_EAN13 = 0x2a, # 1=Enable, 0=Disable, default = disabled
    CONVERT_EAN8_TO_EAN13_TYPE = 0x37, # 1=Enable, 0=Disable, default = disabled
    SEND_UPCA_CHECK_DIGIT = 0x2b, # 1=Enable, 0=Disable, default = enabled
    SEND_UPCE_CHECK_DIGIT = 0x2c, # 1=Enable, 0=Disable, default = enabled
    CODE39_CHECK_DIGIT = 0x2e, # 1=Enable, 0=Disable, default = disabled
    XMIT_CODE39_CHECK_DIGIT = 0x2d, # 1=Enable, 0=Disable, default = disabled
    UPCE_PREAMBLE = 0x25, # 0=None, 1=System char, 2=System char + country code, default=1 system char
    EAN128 = 0x34, # 1=Enable, 0=Disable, default = enabled
    COUPON_CODE = 0x38, # 1=Enable, 0=Disable, default = enabled
    I2OF5 = 0x3a, # 1=Enable, 0=Disable, default = enabled
    I2OF5_CHECK_DIGIT = 0x41, # 1=Enable, 0=Disable, default = disabled
    XMIT_I2OF5_CHECK_DIGIT = 0x40, # 1=Enable, 0=Disable, default = disabled
    CONVERT_ITF14_TO_EAN13 = 0x3f, # 1=Enable, 0=Disable, default = disabled
    I2OF5_LENGTH1 = 0x3B, # L1 = length, L2 = 0 L1 > L2 L1 < L2 L1= 0, L2 = 0, default=L1=14 L2=0
    I2OF5_LENGTH2 = 0x3C, # same as above
    D2OF5 = 0x39, # 1=Enable, 0=Disable, default = disabled
    D2OF5_LENGTH1 = 0x3d,
    D2OF5_LENGTH2 = 0x3e,
    UPC_EAN_SECURITY_LEVEL = 0x2f, # 0 -- 3, default=0
    UPC_EAN_SUPPLEMENTAL_REDUNDANCY = 0x30, # 2--20, default=5
)

DeviceParameters = enum(
    SCANNER_ON_TIME = 0x11, # 1sec -- 10sec, 100msec incremeent, default=30 (3sec)
    VOLUME = 0x02, # 0=off, 1=on, default=1
    COMM_AWAKE_TIME = 0x20, # 1 -- 6 (20seconds -- 2 minutes in 20sec increments), default=20seconds
    BAUD_RATE = 0x0d, # 3=300 4=600 5=1200 6=2400 7=4800 8=9600 9=19200, default 9600
    BAUD_SWITCH_DELAY = 0x1d, # 0 -- 1 second in 10ms increments, default=35 (350ms)
    RESET_BAUD_RATES = 0x1c, # 1=Enable, 0=Disable, default = enabled
    REJECT_REDUNDANT_BARCODE = 0x04, # 1=Enable, 0=Disable, default = disabled
    HOST_CONNECT_BEEP = 0x0a, # 1=Enable, 0=Disable, default = enabled
    HOST_COMPLETE_BEEP = 0x0b, # 1=Enable, 0=Disable, default = enabled
    LOW_BATTERY_INDICATION = 0x07, #0=no indication/no operation, 1=no indication/allow operation, 2=indicate/no operation, 3=indicate/allow operation, default=3
    AUTO_CLEAR = 0x0f, # 1=Enable, 0=Disable, default = disabled
    DELETE_ENABLE = 0x21, #0=delete disabled/clear all disabled, 1=delete disabled/clear all enabled, 2=delete enabled/clear all disabled, 3=delete enabled/creal all enabled, 4=Radio stamp, 5=VDIU voluntary device initiated upload, default=3
    DATA_PROTECTION = 0x31, # 1=Enable, 0=Disable, default = disabled
    MEMORY_FULL_INDICATION = 0x32, # 1=Enable, 0=Disable, default = enabled
    MEMORY_LOW_INDICATION = 0x33, # 1=Enable, 0=Disable, default = disabled
    MAX_BARCODE_LEN = 0x22, # 1--30 default=30
    GOOD_DECODE_LED_ON_TIME = 0x1e, # 250ms--1sec 250ms increment, default = 4
    STORE_RTC = 0x23, # 1=Enable, 0=Disable, default = enabled
    ASCII_MODE = 0x4f, # 0=Like encrypted data, 1=as ascii string, default=0
    BEEPER_TOGGLE = 0x55, # 0=No 1=Yes, default=1
    BEEPER_AUTO_ON = 0x56, # 0=No 1=Yes, default=0
    SCRATCH_PAD = 0x26
)

class OpticonAPI(object):
    def __init__(self, stream):
        self.stream = stream

    def send_frame(self, frame):
        self.stream.write(frame.build())

    def receive_frame(self, cls):
        frame = cls()
        frame.receive(self.stream)
        return frame


    def interrogate(self):
        self.send_frame(InterrogateRequestFrame())
        return self.receive_frame(InterrogateResponseFrame)

    def set_time(self, date=datetime.datetime.now()):
        self.send_frame(SetTimeRequestFrame(date))
        return self.receive_frame(SetTimeResponseFrame)

    def get_param(self, param):
        self.send_frame(GetParamRequestFrame(param))
        return self.receive_frame(GetParamResponseFrame)

    def set_param(self, param, value):
        self.send_frame(SetParamRequestFrame(param, value))
        return self.receive_frame(SetParamResponseFrame)

    def get_data(self):
        self.send_frame(GetDataRequestFrame())
        return self.receive_frame(GetDataResponseFrame)

class Frame(object):
    """
        byte   opcode
        byte   unknown // Always 2
        bit[3] unknown
        bit[5] length
        byte[length] payload
        byte   pad  // Only exist if length > 0
        uint16 crc16
    """

    def __init__(self, opcode=0, unk1=2, unk2=0, payload=''):
        self.raw = ''

        self.opcode = opcode
        self.payload = payload

        self.unk1 = unk1
        self.unk2 = unk2
        self.length = len(self.payload)

    def build(self):
        self.length = len(self.payload)

        data = struct.pack('>BBB%ds' % (self.length),
            self.opcode,
            self.unk1,
            ((self.unk2 & 0x7) << 5) | (self.length & 0x1f),
            self.payload
        )

        if self.length > 0:
            data += chr(0)

        data += struct.pack('>H', calculate_crc(data))
        return data

    def _stream_read(self, stream, length):
        data = stream.read(length)
        self.raw += data
        return data

    def receive_data(self, stream):
        length = struct.unpack('B', self._stream_read(stream, 1))[0]
        self.unk2 = (length >> 5) & 0x7 # Don't know what the three most significant bits are
        self.length = length & 0x1f

        # Get the frame payload
        # self.payload = struct.unpack('B'*self.length, self._stream_read(stream, self.length))
        self.payload = self._stream_read(stream, self.length)
        self.parse_payload()

        # If the length was greater than 0 then the frame contains a zero after the payload
        if self.length > 0:
            self._stream_read(stream, 1)

        # Get the frame checksum
        self.crc = struct.unpack('>H', self._stream_read(stream, 2))[0]

        # Verify the crc
        if calculate_crc(self.raw[:-2]) != self.crc:
            raise InvalidFrameException()

    def parse_payload(self):
        """Not implemented in the generic frame."""
        pass

    def receive(self, stream):
        # Get the frame header information
        self.opcode, self.unk1 = struct.unpack('BB', self._stream_read(stream, 2))

        self.receive_data(stream)




class InterrogateRequestFrame(Frame):
    def __init__(self):
        super(InterrogateRequestFrame, self).__init__(opcode=1)

class InterrogateResponseFrame(Frame):
    def parse_payload(self):
        self.deviceId, self.firmwareVersion = struct.unpack('>xQ8s', self.payload)

class SetTimeRequestFrame(Frame):
    def __init__(self, date):
        super(SetTimeRequestFrame, self).__init__(opcode=9, payload=dateToTimestamp(date))

class SetTimeResponseFrame(Frame):
    def parse_payload(self):
        self.second, self.minute, self.hour, self.day, self.month, self.year = struct.unpack('>BBBBBB', self.payload)
        self.year += 2000
        self.date = datetime.datetime(self.year, self.month, self.day, self.hour, self.minute, self.second)

class GetParamRequestFrame(Frame):
    def __init__(self, param):
        super(GetParamRequestFrame, self).__init__(opcode=8, payload=struct.pack('>B', param))

class GetParamResponseFrame(Frame):
    def parse_payload(self):
        self.param, self.param_value = struct.unpack('>BB', self.payload)

class SetParamRequestFrame(Frame):
    def __init__(self, param, value):
        super(SetParamRequestFrame, self).__init__(opcode=3, payload=struct.pack('>BB', param, value))

class SetParamResponseFrame(GetParamResponseFrame):
    pass

class Barcode(object):
    def __init__(self, symbology, barcode, timestamp):
        self.symbology = symbology
        self.barcode = barcode
        self.timestamp = timestamp

class GetDataRequestFrame(Frame):
    def __init__(self):
        super(GetDataRequestFrame, self).__init__(opcode=7)

class GetDataResponseFrame(Frame):
    def receive_data(self, stream):
        self.deviceId = struct.unpack('>Q', self._stream_read(stream, 8))[0]
        self.barcodes = []
        while True:
            length = struct.unpack('B', self._stream_read(stream, 1))[0]
            if length == 0:
                break

            symbology_id, barcode, timestamp = struct.unpack('>B%dsI' % (length - 5), self._stream_read(stream, length))
            self.barcodes.append(Barcode(symbology_id, barcode, timestampToDate(timestamp)))



ser = serial.Serial(
    port='COM4',
    baudrate=9600,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
)

api = OpticonAPI(ser)

res = api.interrogate()
print res.deviceId, res.firmwareVersion

res = api.set_time()
print res.date

res = api.get_param(DeviceParameters.ASCII_MODE) # ascii mode
print res.param_value

res = api.get_data()
for barcode in res.barcodes:
    print '[{}] {} {}'.format(barcode.symbology, barcode.barcode, barcode.timestamp)
