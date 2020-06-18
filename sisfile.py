#!/usr/bin/env python3

import os
from enum import IntEnum
from util.binfile import (
    Structure,
    Attribute,
    StructurePayloadLength,
    CanBeLast,
    SkipNextIfByte,
    EfficientUInt63,
    BuildEnum,
    Zlib,
    Int32,
    UInt64,
    UInt32,
    UInt16,
    UInt8,
    UTF16String,
    Array,
    UnknownPayload,
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
    C, EN = range(2) # made-up names

class SISField(Structure):
    _subclassfield = 'Type'
    ALIGNMENT = 4
    Type : BuildEnum(TInt32, TField)
    Length : EfficientUInt63
    Length : StructurePayloadLength

class SISString(SISField):
    # UCS-2 encoded unicode string
    String : UTF16String # made-up name

class SISArray(SISField):
    _template = '_tp',
    SISFieldType : BuildEnum(TUint32, TField)
    Contents : Array['_tp'] # made-up name

    def init_common(self, obj):
        obj.Type = self.SISFieldType

class SISCompressed(SISField):
    _subclassfield = 'Algorithm'
    _template = '_tp',
    Algorithm : BuildEnum(TUint32, TCompressionAlgorithm)
    UncompressedDataSize : TUint64

class SISCompressedNone(SISCompressed):
    CompressedData : '_tp'

class SISCompressedDeflate(SISCompressed):
    CompressedData : Zlib['_tp']

    def init_common(self, obj):
        obj._maxfin = self.UncompressedDataSize

class SISVersion(SISField):
    Length = 12
    # -1 means Any
    Major : TInt32
    Minor : TInt32
    Build : TInt32

class SISVersionRange(SISField):
    # Length = 40  # can be 20 as well
    FromVersion : SISVersion
    FromVersion : CanBeLast
    ToVersion : SISVersion

class SISDate(SISField):
    Length = 4
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
    Length = 4
    UID1 : TInt32

class SISLanguage(SISField):
    Length = 4
    Language : BuildEnum(TUint32, TLanguage)

class SISBlob(SISField):
    Blob : UnknownPayload

class SISDataIndex(SISField):
    Length = 4
    DataIndex : TUint32

# reordered before SISContents:
class SISControllerChecksum(SISField):
    Length = 2
    Checksum : TUint16 # CRC-16

class SISDataChecksum(SISField):
    Length = 2
    Checksum : TUint16 # CRC-16

# reordered before SISController:
class SISInfo(SISField):
    UID : SISUid
    VendorUniqueName : SISString
    Names : SISArray[SISString]
    VendorNames : SISArray[SISString]
    Version : SISVersion
    CreationTime : SISDateTime
    InstallType : TUint8 # TInstallType
    InstallFlags : TUint8 # TInstallFlags

class SISSupportedLanguages(SISField):
    Languages : SISArray[SISLanguage]

# reordered before SISSupportedOptions:
class SISSupportedOption(SISField):
    Names : SISArray[SISString]

class SISSupportedOptions(SISField):
    Options : SISArray[SISSupportedOption]

# reordered before SISPrerequisites
class SISDependency(SISField):
    UID : SISUid
    VersionRange : SISVersionRange
    DependencyNames : SISArray[SISString]

class SISPrerequisites(SISField):
    TargetDevices : SISArray[SISDependency]
    Dependencies : SISArray[SISDependency]

# reordered before SISProperties
class SISProperty(SISField):
    Length = 8
    Key : TInt32
    Value : TInt32

class SISProperties(SISField):
    Properties : SISArray[SISProperty]

# reordered before SISFileDescription
class SISCapabilities(SISField):
    Capabilities : Array[TUint32] # bitfield

class SISHash(SISField):
    HashAlgorithm : TUint32 # TSISHashAlgorithm
    HashData : SISBlob

# reordered before SISLogo
class SISFileDescription(SISField):
    Target : SISString
    MIMEType : SISString

    MIMEType : SkipNextIfByte('Capabilities', TField.SISHash & 255)
    # "This field is optional"
    Capabilities : SISCapabilities
    Hash : SISHash
    Operation : TUint32
    OperationOptions : TUint32
    FileLength : TUint64 # originally called Length, but clashes with SISField.Length
    UncompressedLength : TUint64
    FileIndex : TUint32

# reordered before SISController
class SISLogo(SISField):
    LogoFile : SISFileDescription

class SISInstallBlock(SISField):
    Files : SISArray[SISFileDescription]
    EmbeddedSISFiles : SISArray[SISField] # should be SISControllers
    IfBlocks : SISArray[SISField] # should be SISIf

# reordered before SISSignatureCertificateChain
class SISCertificateChain(SISField):
    CertificateData : SISBlob

# reordered before SISSignature
class SISSignatureAlgorithm(SISField):
    # Supported values:
    # * “1.2.840.113549.1.1.5” - SHA-1 with RSA signature
    # * “1.2.840.10040.4.3”    - SHA-1 with DSA signature
    AlgorithmIdentifier : SISString

class SISSignature(SISField):
    SignatureAlgorithm : SISSignatureAlgorithm
    SignatureData : SISBlob

class SISSignatureCertificateChain(SISField):
    Signatures : SISArray[SISSignature]
    CertificateChain : SISCertificateChain

class SISController(SISField):
    Info : SISInfo
    Options : SISSupportedOptions
    Languages : SISSupportedLanguages
    Prerequisites : SISPrerequisites
    Properties : SISProperties

    Properties : SkipNextIfByte('Logo', TField.SISInstallBlock & 255)
    # "This field is optional"
    Logo : SISLogo
    InstallBlock : SISInstallBlock
    Signature0 : SISSignatureCertificateChain
    DataIndex : SISDataIndex

# reordered before SISDataUnit
class SISFileData(SISField):
    FileData : SISCompressed[UnknownPayload]

# reordered before SISData
class SISDataUnit(SISField):
    FileData : SISArray[SISFileData]

class SISData(SISField):
    DataUnits : SISArray[SISDataUnit]

class SISContents(SISField):
    ControllerChecksum : SISControllerChecksum
    DataChecksum : SISDataChecksum
    Controller : SISCompressed[SISController]
    Data : SISData

# reordered before SISIf
class SISExpression(SISField):
    Operator : TUint32 # TOperator
    IntegerValue : TInt32
    StringValue : SISString
    StringValue : CanBeLast
    LeftExpression : SISField # should be SISExpression
    LeftExpression : CanBeLast
    RightExpression : SISField # should be SISExpression

class SISElseIf(SISField):
    Expression : SISExpression
    InstallBlock : SISInstallBlock

class SISIf(SISField):
    Expression : SISExpression
    InstallBlock : SISInstallBlock
    ElseIfs : SISArray[SISElseIf]

def extract_files(fp, target_dir):
    ff = SISField(fp)
    for f in ff.Controller.CompressedData.InstallBlock.Files.Contents:
        fd = ff.Data.DataUnits.Contents[0].FileData.Contents[f.FileIndex]
        print(fd.FileData.CompressedData)
        print(f.Target)
        print(f.MIMEType)
        name = os.path.join(target_dir, f.Target.String.split('\\')[-1] or "%d"%f.FileIndex)
        with open(name, 'wb') as ofp:
            ofp.write(fd.FileData.CompressedData)
