#!/usr/bin/env python3

from enum import IntEnum
from util.binfile import (
    Structure,
    StructurePayloadLength,
    EfficientUInt63,
    BuildEnum,
    Zlib,
    Int32,
    UInt64,
    UInt32,
    UInt16,
    UInt8,
)

# based on format documentation from:
# https://web.archive.org/web/20101011053920/http://developer.symbian.org/wiki/images/b/b7/SymbianOSv9.x_SIS_File_Format_Specification.pdf

TInt32 = Int32
TUint64 = UInt64
TUint32 = UInt32
TUint16 = UInt16
TUint8 = UInt8

class SymbianFileHeader(Structure):
    UID1 : TInt32 = 0x10201A7A
    UID2 : TInt32 = 0
    UID3 : TInt32
    UIDChecksum : TInt32

class TField(IntEnum):
    (
        INVALID,
        SISString,
        SISArray,
        SISCompressed,
        SISVersion,
        SISVersionRange,
        SISDate,
        SISTime,
        SISDateTime,
        SISUid,
        UNUSED,
        SISLanguage,
        SISContents,
        SISController,
        SISInfo,
        SISSupportedLanguages,
        SISSupportedOptions,
        SISPrerequisites,
        SISDependency,
        SISProperties,
        SISProperty,
        SISSignatures,
        SISCertificateChain,
        SISLogo,
        SISFileDescription,
        SISHash,
        SISIf,
        SISElseIf,
        SISInstallBlock,
        SISExpression,
        SISData,
        SISDataUnit,
        SISFileData,
        SISSupportedOption,
        SISControllerChecksum,
        SISDataChecksum,
        SISSignature,
        SISBlob,
        SISSignatureAlgorithm,
        SISSignatureCertificateChain,
        SISDataIndex,
        SISCapabilities,
    ) = range(42)

class TCompressionAlgorithm(IntEnum):
    SISCompressedNone, SISCompressedDeflate = range(2)

class TLanguage(IntEnum):
    C = 0

class SISField(Structure):
    _subclassfield = 'Type'
    ALIGNMENT = 4
    Type : BuildEnum(TInt32, TField)
    Length : EfficientUInt63
    Length : StructurePayloadLength

#class SISString(SISField):
    pass

#class SISArray(SISField):
    pass

class SISCompressed(SISField):
    _subclassfield = 'Algorithm'
    _template = '_tp',
    Algorithm : BuildEnum(TUint32, TCompressionAlgorithm)
    UncompressedDataSize : TUint64

class SISCompressedNone(SISCompressed):
    CompressedData : '_tp'

class SISCompressedDeflate(SISCompressed):
    CompressedData : Zlib['_tp']

class SISVersion(SISField):
    # -1 means Any
    Major : TInt32
    Minor : TInt32
    Build : TInt32

class SISVersionRange(SISField):
    FromVersion : SISVersion
    ToVersion : SISVersion

class SISDate(SISField):
    Year : TUint16
    Month : TUint8 # zero-based
    Day : TUint8 # one-based

class SISTime(SISField):
    Hours : TUint8
    Minutes : TUint8
    Seconds : TUint8

class SISDateTime(SISField):
    Date : SISDate
    Time : SISTime

# UNUSED here

class SISUid(SISField):
    # is to match UID3 from file header
    UID1 : TInt32

class SISLanguage(SISField):
    Language : BuildEnum(TUint32, TLanguage)

#class SISBlob(SISField):
    pass

class SISDataIndex(SISField):
    DataIndex : TUint32

# reordered before SISContents:
class SISControllerChecksum(SISField):
    Checksum : TUint16 # CRC-16

class SISDataChecksum(SISField):
    Checksum : TUint16 # CRC-16

class SISController(SISField):
#    Info : SISInfo
#    Options : SISSupportedOptions
#    Languages : SISSupportedLanguages
#    Prerequisites : SISPrerequisites
#    Properties : SISProperties
#    Logo : SISLogo
#    InstallBlock : SISInstallBlock
#    Signature0 : SISSignatureCertificateChain
#    DataIndex : SISDataIndex
    pass

class SISData(SISField):
# EEEE
    pass

class SISContents(SISField):
    ControllerChecksum : SISControllerChecksum
    DataChecksum : SISDataChecksum
    Controller : SISCompressed[SISController]
    Data : SISData
