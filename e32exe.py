#!/usr/bin/env python3

import array
import time
from enum import IntEnum
from util.binfile import (
    Structure,
    Attribute,
    StructurePayloadLength,
    StructureMeta,
    get_base_type,
    CanBeLast,
    SkipNextIfByte,
    EfficientUInt63,
    BuildEnum,
    Zlib,
    Int32,
    Int16,
    Int8,
    UInt64,
    UInt32,
    UInt16,
    UInt8,
    UTF16String,
    Array,
    UnknownPayload,
)

TInt = Int32
TInt16 = Int16
TInt8 = Int8
TUint32 = TUint = UInt32
TUint16 = UInt16

crc16tab = array.array('H', [
    0x0000,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,0x8108,0x9129,0xa14a,
    0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef,0x1231,0x0210,0x3273,0x2252,0x52b5,0x4294,
    0x72f7,0x62d6,0x9339,0x8318,0xb37b,0xa35a,0xd3bd,0xc39c,0xf3ff,0xe3de,0x2462,
    0x3443,0x0420,0x1401,0x64e6,0x74c7,0x44a4,0x5485,0xa56a,0xb54b,0x8528,0x9509,
    0xe5ee,0xf5cf,0xc5ac,0xd58d,0x3653,0x2672,0x1611,0x0630,0x76d7,0x66f6,0x5695,
    0x46b4,0xb75b,0xa77a,0x9719,0x8738,0xf7df,0xe7fe,0xd79d,0xc7bc,0x48c4,0x58e5,
    0x6886,0x78a7,0x0840,0x1861,0x2802,0x3823,0xc9cc,0xd9ed,0xe98e,0xf9af,0x8948,
    0x9969,0xa90a,0xb92b,0x5af5,0x4ad4,0x7ab7,0x6a96,0x1a71,0x0a50,0x3a33,0x2a12,
    0xdbfd,0xcbdc,0xfbbf,0xeb9e,0x9b79,0x8b58,0xbb3b,0xab1a,0x6ca6,0x7c87,0x4ce4,
    0x5cc5,0x2c22,0x3c03,0x0c60,0x1c41,0xedae,0xfd8f,0xcdec,0xddcd,0xad2a,0xbd0b,
    0x8d68,0x9d49,0x7e97,0x6eb6,0x5ed5,0x4ef4,0x3e13,0x2e32,0x1e51,0x0e70,0xff9f,
    0xefbe,0xdfdd,0xcffc,0xbf1b,0xaf3a,0x9f59,0x8f78,0x9188,0x81a9,0xb1ca,0xa1eb,
    0xd10c,0xc12d,0xf14e,0xe16f,0x1080,0x00a1,0x30c2,0x20e3,0x5004,0x4025,0x7046,
    0x6067,0x83b9,0x9398,0xa3fb,0xb3da,0xc33d,0xd31c,0xe37f,0xf35e,0x02b1,0x1290,
    0x22f3,0x32d2,0x4235,0x5214,0x6277,0x7256,0xb5ea,0xa5cb,0x95a8,0x8589,0xf56e,
    0xe54f,0xd52c,0xc50d,0x34e2,0x24c3,0x14a0,0x0481,0x7466,0x6447,0x5424,0x4405,
    0xa7db,0xb7fa,0x8799,0x97b8,0xe75f,0xf77e,0xc71d,0xd73c,0x26d3,0x36f2,0x0691,
    0x16b0,0x6657,0x7676,0x4615,0x5634,0xd94c,0xc96d,0xf90e,0xe92f,0x99c8,0x89e9,
    0xb98a,0xa9ab,0x5844,0x4865,0x7806,0x6827,0x18c0,0x08e1,0x3882,0x28a3,0xcb7d,
    0xdb5c,0xeb3f,0xfb1e,0x8bf9,0x9bd8,0xabbb,0xbb9a,0x4a75,0x5a54,0x6a37,0x7a16,
    0x0af1,0x1ad0,0x2ab3,0x3a92,0xfd2e,0xed0f,0xdd6c,0xcd4d,0xbdaa,0xad8b,0x9de8,
    0x8dc9,0x7c26,0x6c07,0x5c64,0x4c45,0x3ca2,0x2c83,0x1ce0,0x0cc1,0xef1f,0xff3e,
    0xcf5d,0xdf7c,0xaf9b,0xbfba,0x8fd9,0x9ff8,0x6e17,0x7e36,0x4e55,0x5e74,0x2e93,
    0x3eb2,0x0ed1,0x1ef0
])

def crc16(bts):
    crc = 0
    for b in bts:
        crc = (crc << 8 ^ crc16tab[b ^ crc >> 8 & 0xff]) & 0xffff
    return crc

def uidcrc(u1, u2, u3):
    b = u1._tobytes() + u2._tobytes() + u3._tobytes()
    return crc16(b[1::2]) << 16 | crc16(b[::2])

class timeint(int):
    # This number is huge. Dividing it by 1000 is not enough.
    # Even dividing it by 1 000 000 is not enough.
    # It actually turns out that it is not *milliseconds* since 2000,
    # but *nanoseconds* since 0 AD.

    # This is a lesson to file format designers. Think twice before inventing
    # your own custom timestamp format and use (either integer,
    # floating point, or fixed point, does not really matter):
    #  a) Unix timestamp (well documented, portable, and widely used)
    #  b) Some intelligent string format (yes, this is good, too)
    #  c) If you truly must use something else, use Julian day, like those
    #     nonsense spreadsheets do.
    #  d) Oh wait you can also use this forma^UNEVER REUSE THIS FORMAT. EVER.

    def __repr__(self):
        return time.ctime(self / 1e6 + time.mktime((0,)*9))
Millis64Since2000 = StructureMeta.from_struct('Q', name='Millis64Since2000', bases=get_base_type(timeint))

class TVersion(Structure):
    iMajor : TInt8
    iMinor : TInt8
    iBuild : TInt16

class ValidateUidChecksum(Attribute):
    @staticmethod
    def mkvalidator(key):
        def ret(self):
            value = getattr(self, key)
            crc = uidcrc(self.iUid1, self.iUid2, self.iUid3)
            if value != crc:
                raise ValueError(f"Incorrect crc: {value:x} (correct: {crc:x})")
        return ret

class TCpu(IntEnum):
    ECpuUnknown = 0
    ECpuX86 = 0x1000
    ECpuArmV4 = 0x2000
    ECpuArmV5 = 0x2001
    ECpuArmV6 = 0x2002
    ECpuMCore = 0x4000

class E32ImageHeader(Structure):
    iUid1 : TUint32				# KDynamicLibraryUidValue or KExecutableImageUidValue
    iUid2 : TUint32				# Second UID for executable.
    iUid3 : TUint32				# Third UID for executable.
    iUidChecksum : TUint32		# Checksum for iUid1, iUid2 and iUid3.
    iUidChecksum : ValidateUidChecksum
    iSignature : TUint = int.from_bytes(b'EPOC', 'little')	# Contains 'EPOC'.
    iHeaderCrc : TUint32			# CRC-32 of entire header. @see #KImageCrcInitialiser.
    iModuleVersion : TUint32		# Version number for this executable (used in link resolution).
    iCompressionType : TUint32	# Type of compression used for file contents located after the header. (UID or 0 for none).
    iToolsVersion : TVersion		# Version number of tools which generated this file.
    #iTimeLo : TUint32			# Least significant 32 bits of the time of image creation, in milliseconds since since midnight Jan 1st, 2000.
    #iTimeHi : TUint32			# Most significant 32 bits of the time of image creation, in milliseconds since since midnight Jan 1st, 2000.
    iTime : Millis64Since2000
    iFlags : TUint				# Contains various bit-fields of attributes for the image.
    iCodeSize : TInt				# Size of executables code. Includes import address table, constant data and export directory.
    iDataSize : TInt				# Size of executables initialised data.
    iHeapSizeMin : TInt			# Minimum size for an EXEs runtime heap memory.
    iHeapSizeMax : TInt			# Maximum size for an EXEs runtime heap memory.
    iStackSize : TInt			# Size for stack required by an EXEs initial thread.
    iBssSize : TInt				# Size of executables uninitialised data.
    iEntryPoint : TUint			# Offset into code of the entry point.
    iCodeBase : TUint			# Virtual address that the executables code is linked for.
    iDataBase : TUint			# Virtual address that the executables data is linked for.
    iDllRefTableCount : TInt		# Number of executable against which this executable is linked. The number of files mention in the import section at iImportOffset.
    iExportDirOffset : TUint		# Byte offset into file of the export directory.
    iExportDirCount : TInt		# Number of entries in the export directory.
    iTextSize : TInt				# Size of just the text section, also doubles as the offset for the Import Address Table w.r.t. the code section.
    iCodeOffset : TUint			# Offset into file of the code section. Also doubles the as header size.
    iDataOffset : TUint			# Offset into file of the data section.
    iImportOffset : TUint		# Offset into file of the import section (E32ImportSection).
    iCodeRelocOffset : TUint		# Offset into file of the code relocation section (E32RelocSection).
    iDataRelocOffset : TUint		# Offset into file of the data relocation section (E32RelocSection).
    iProcessPriority : TUint16	# Initial runtime process priorty for an EXE. (Value from enum TProcessPriority.)
    #iCpuIdentifier : TUint16		# Value from enum TCpu which indicates the CPU architecture for which the image was created
    iCpuIdentifier : BuildEnum(TUint16, TCpu)

def objcopy(fp, target_dir):
    pass
