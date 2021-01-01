
import os
import zlib
import time
from enum import Enum, EnumMeta
from io import BytesIO
from struct import Struct

def TellFile(fp):
    return fp

class Unknown(float):
    def __repr__(self):
        return "UNKNOWN"
    def __add__(self, o):
        return self
    __radd__ = __add__

UNKNOWN = Unknown('inf')

class Attribute:
    @staticmethod
    def mkvalidator(key):
        return lambda self: None

    @staticmethod
    def preparsehook(key):
        return lambda self: {}

    @staticmethod
    def parsedhook(key):
        return lambda self: None

class StructurePayloadLength(Attribute):
    @staticmethod
    def mkvalidator(key):
        def ret(self):
            value = getattr(self, key)
            actual = self._fin - self._actual_roffsets[key]
            padsize = -actual % self.ALIGNMENT
            if value < actual or value > actual + padsize:
                raise ParseError(f"{type(self).__name__} at offset {self._at}: "
                                 f"payload was to be {value} bytes long, "
                                 f" but {actual} bytes were parsed.")
        return ret

    @staticmethod
    def parsedhook(key):
        def ret(self):
            value = getattr(self, key)
            self._maxfin = self._actual_roffsets[key] + value
            #print(f"Fixed maxfin to {self._maxfin=}")
        return ret

class CountIn(Attribute):
    def __init__(self, field):
        self._field = field

    def preparsehook(self, key):
        def ret(self2):
            value = getattr(self2, self._field)
            return {'_maxcount': value}
        return ret

class CanBeLast(Attribute):
    @staticmethod
    def parsedhook(key):
        def ret(self):
            if self._actual_roffsets[key] == self._maxfin:
                return True
        return ret

class SkipNextIfByte(Attribute):
    def __init__(self, nextkey, byte):
        self.nextkey = nextkey
        self.byte = byte

    def parsedhook(skip, key):
        def ret(self):
            value = getattr(self, key)
            if self._peekbyte() == skip.byte:
                setattr(self, skip.nextkey, None)
        return ret


class StructureAnnotations(dict):
    def __init__(self, pardict):
        self.pardict = pardict
        super().__init__()
    def __setitem__(self, key, val):
        if key in self:
            self.pardict['_validators'].append(val.mkvalidator(key))
            self.pardict['_hooks']['__post_' + key] = val.parsedhook(key)
            self.pardict['_hooks']['__pre_' + key] = val.preparsehook(key)
            return
        self.pardict['_offsets'][key] = self.pardict['SIZE']
        if isinstance(val, Structure):
            self.pardict['SIZE'] += val.SIZE
        else:
            self.pardict['SIZE'] = UNKNOWN
        return super().__setitem__(key, val)

class ParseError(ValueError):
    pass

class TemplateNeeded(ValueError):
    pass

class StructureMeta(type):
    @classmethod
    def __prepare__(meta, name, bases):
        d = {}
        d.update({
            '__annotations__': StructureAnnotations(d),
            '_subclassfield': None,
            '_offsets': {},
            '_validators': [],
            '_hooks': {},
            'SIZE': 0,
        })
        for base in bases:
            if hasattr(base, 'SIZE'):
                d['SIZE'] = base.SIZE
            if hasattr(base, '_validators'):
                d['_validators'].extend(base._validators)
            if hasattr(base, '_offsets'):
                d['_offsets'].update(base._offsets)
            if hasattr(base, '_hooks'):
                d['_hooks'].update(base._hooks)
        return d

    @classmethod
    def from_ctypes(meta, ctypes_struct):
        pass

    @classmethod
    def __new__(meta, metacl, name, bases, dic):
        annotations_all = {}
        for base in bases:
            annotations_all.update(getattr(base, '__annotations_all__', ()))
        annotations_all.update(dic.get('__annotations__', ()))
        dic['__annotations_all__'] = annotations_all
        if hasattr(dic.get('_struct'), 'size'):
            dic['SIZE'] = dic['_struct'].size
        cls = type.__new__(metacl, name, bases, dic)
        subclassfield = getattr(cls.__base__, '_subclassfield', None)
        if subclassfield:
            try:
                setattr(cls, subclassfield,
                        getattr(cls.__base__.__annotations__[subclassfield], cls.__name__))
            except AttributeError:
                pass
        return cls

    @classmethod
    def from_struct(meta, struc, *, bases=None, name='[anon]', named=None):
        if not isinstance(struc, Struct):
            struc = Struct(struc)
        if bases is None:
            bases = Structure,
        elif isinstance(bases, type):
            bases = bases,
        dic = meta.__prepare__(name, bases)
        dic['_struct'] = dic['_rdstruct'] = struc
        return meta(name, bases, dic)

    def _instantiate(cls, args):
        cls = type(cls)(cls.__name__, (cls,), cls.__dict__.copy())
        cls._template_args = args
        template = list(cls._template)
        for field, tp in cls.__annotations_all__.items():
            if tp in args:
                cls.__annotations_all__[field] = args[tp]
            elif issubclass(tp, Structure):
                cls.__annotations_all__[field] = tp._instantiate(args)
        for pattern, value in args.items():
            try:
                idx = template.index(pattern)
            except ValueError:
                continue
            if isinstance(value, str):
                template[template.index(pattern)] = value
            else:
                del template[idx]
                setattr(cls, pattern, value)
        cls._template = tuple(filter(bool, template))
        return cls

    def get_subclasses(cls):
        if cls._template_args:
            for sub in cls.__base__.get_subclasses():
                yield sub._instantiate(cls._template_args)
        else:
            yield from filter(cls.__name__.__ne__, cls.__subclasses__())

    def __getitem__(cls, args):
        if not isinstance(args, tuple):
            args = args,
        return cls._instantiate(dict(zip(cls._template, args)))

class Structure(metaclass=StructureMeta):
    _template = ()
    _template_args = ()
    ALIGNMENT = 1

    @classmethod
    def _readstruct(cls, parsefile):
        return cls._rdstruct.unpack(parsefile.read(cls.SIZE))

    @staticmethod
    def _parsefile(parseobj):
        if isinstance(parseobj, tuple):
            parseobj, maxfin = parseobj
        else:
            maxfin = None
        if hasattr(parseobj, 'read'):
            return TellFile(parseobj), maxfin
        return BytesIO(parseobj), maxfin

    def _validate(self):
        for validator in self._validators:
            validator(self)

    def _tobytes(self):
        return self._struct.pack(self)

    @classmethod
    def __new__(cls, subcl, parseobj=None, parsefile=None, init_common=None):
        if cls._template:
            raise TemplateNeeded(cls.__name__)
        if isinstance(parseobj, Structure):
            self = super().__new__(subcl)
            self.__dict__.update(parseobj.__dict__)
            maxfin = self._maxfin
        else:
            parsefile, maxfin = cls._parsefile(parseobj)
            self = super().__new__(subcl)
            self._actual_offsets = {}
            self._actual_roffsets = {}
        if parseobj is None:
            return self
        self._at = offset = parsefile.tell()
        padlen = -offset % cls.ALIGNMENT
        if padlen:
            padding = parsefile.read(-offset % cls.ALIGNMENT)
            if any(padding):
                raise ParseError(f"nonzero padding at offset {offset}")
            self._at = offset = offset + padlen
        if maxfin is None:
            #print(f"{subcl.__name__}: guessing maxfin: {self.SIZE=}")
            maxfin = offset + self.SIZE
        self._maxfin = maxfin
        if init_common:
            init_common(self)
        self._file = parsefile
        try:
            return self._parse(parsefile)
        finally:
            self._file = None

    def _peekbyte(self):
        if self._file is None:
            raise EOFError("cannot peek when parsing is done")
        byte, = self._file.read(1)
        self._file.seek(-1, os.SEEK_CUR)
        return byte

    def _parse(self, parsefile):
        self._file = parsefile
        cls = subcl = type(self)
        offset = self._at
        if hasattr(cls, '_struct'):
            vals = self._readstruct(parsefile)
            if cls._named:
                namemap = cls._named(*vals)._asdict()
            else:
                namemap = dict(enumerate(vals))
            self.__dict__.update(namemap)
            for k, v in namemap.items():
                # TODO
                self._actual_offsets[k] = offset
                self._actual_roffsets[k] = parsefile.tell()
        retype = False
        for field, tp in cls.__annotations_all__.items():
            if field in self.__dict__:
                continue
            #print(f"{subcl.__name__} at offset {offset}: "
            #      f"parsing a {tp} {field}\n ({self.__dict__=})")
            self._actual_offsets[field] = parsefile.tell()
            extra = {}
            if issubclass(tp, (Array, Zlib)):
                try:
                    extra = {'_init_common': self.init_common}
                except AttributeError:
                    pass
            hook = self._hooks.get('__pre_' + field)
            if hook:
                extra.update(hook(self))
            try:
                val = tp((parsefile, self._maxfin), **extra)
            except ValueError:
                raise ParseError(f"{subcl.__name__} at offset {offset}: "
                                 f"invalid {tp.__name__} {field}")
            except TypeError:
                #print(f"{tp=}")
                raise
            self._actual_roffsets[field] = parsefile.tell()
            try:
                defval = getattr(cls, field)
            except AttributeError:
                pass
            else:
                if defval != val:
                    raise ParseError(f"{subcl.__name__} at offset {offset}: "
                                     f"expected {defval}, found {val}")
            if field == self._subclassfield:
                name = val.name
                try:
                    retype = next(c for c in cls.get_subclasses()
                                    if c.__name__ == name)
                except StopIteration:
                    raise RuntimeError(f"subclass {name} not found")
            setattr(self, field, val)

            hook = self._hooks.get('__post_' + field)
            if hook:
                if hook(self):
                    break
        if retype and not issubclass(subcl, retype):
            return retype(self, parsefile=parsefile)
        print(f"Parsed: {self!r}")
        self._fin = parsefile.tell()
        self._validate()
        return self

    def __contains__(self, key):
        return key in self.__annotations_all__

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, val):
        return setattr(self, key, val)

    def _fields(self):
        for key in self.__annotations_all__:
            val = getattr(self, key, None)
            if val != getattr(type(self), key, None):
                yield key, val

    def __repr__(self):
        *f, = self._fields()
        sep = ',\n' if len(f) > 4 else ', '
        fieldrep = sep.join(f"{key}={value!r}" for key, value in f).replace('\n', '\n    ')
        return f"""<{self.__class__.__name__}:  {fieldrep}>"""

def get_base_type(tp, metaclass=StructureMeta):
    class BaseType(tp, Structure, metaclass=metaclass):
        @classmethod
        def __new__(cls, subcl, parseobj):
            if isinstance(parseobj, tp):
                val = parseobj
            else:
                parsefile, _ = cls._parsefile(parseobj)
            self = tp.__new__(subcl, cls._parse(parsefile))
            print(f"Parsed: {self!r}")
            return self
        @classmethod
        def _parse(cls, parsefile):
            val, = cls._readstruct(parsefile)
            return val
        def __repr__(self):
            return f"<{type(self).__name__}: {super().__repr__()}>"
    return BaseType

class hexint(int):
    def __repr__(self):
        return hex(self)

BaseType = get_base_type(hexint)

Int32 = StructureMeta.from_struct('i', name='Int32', bases=BaseType)
Int16 = StructureMeta.from_struct('h', name='Int16', bases=BaseType)
Int8 = StructureMeta.from_struct('b', name='Int8', bases=BaseType)
UInt64 = StructureMeta.from_struct('Q', name='UInt64', bases=BaseType)
UInt32 = StructureMeta.from_struct('I', name='UInt32', bases=BaseType)
UInt16 = StructureMeta.from_struct('H', name='UInt16', bases=BaseType)
UInt8 = StructureMeta.from_struct('B', name='Uint8', bases=BaseType)

class EnumBaseTypeMeta(StructureMeta, EnumMeta):
    pass

def BuildEnum(ft, cls):
    return EnumBaseTypeMeta.from_struct(
        ft._struct.format,
        name=ft.__name__ + cls.__name__,
        bases=get_base_type(cls, metaclass=EnumBaseTypeMeta))

class EfficientUInt63(UInt32):
    @property
    def _struct(self):
        return Struct('I' if self < 0x80000000 else 'Q')
    _rdstruct = Struct('i')

class ZlibReader:
    def __init__(self, fp):
        self._fp = fp
        self._obj = zlib.decompressobj()
        self._off = 0
        self._readbuf = BytesIO()

    def tell(self):
        return self._off

    def seek(self, offset, whence):
        assert whence == os.SEEK_CUR
        assert offset == -1
        assert self._readbuf.tell()

        self._off += offset
        ret = self._readbuf.seek(offset, whence)
        return ret

    def read(self, n):
        if n < 0:
            raise ValueError("No reading everything!!!")
        ret = self._readbuf.read(n)
        if len(ret) < n:
            while len(ret) < n and not self._obj.eof:
                rd = self._fp.read(1)
                #print(f"{rd=}")
                if not rd:
                    ret += self._obj.flush()
                    break
                ret += self._obj.decompress(rd)
                #print(f"{ret=}")
            self._readbuf = BytesIO(ret)
            ret = self._readbuf.read(n)
        self._off += len(ret)
        #print(f'read({n}): {ret!r} ({self._obj=}, {self._obj.eof=})')
        return ret

    def close(self):
        self.read(1)

class Zlib(Structure):
    _template = '_tp',
    @classmethod
    def __new__(cls, subcl, parseobj, _init_common=None):
        if cls._template:
            raise TemplateNeeded(cls.__name__)
        parsefile, _ = cls._parsefile(parseobj)
        zreader = ZlibReader(parsefile)
        ret = cls._tp(zreader, init_common=_init_common)
        zreader.close()
        return ret

class Array(list, Structure):
    _template = '_tp',
    @classmethod
    def __new__(cls, subcl, parseobj, _init_common=None, _maxcount=0x80000000):
        if cls._template:
            raise TemplateNeeded(subcl.__name__)
        self = super().__new__(subcl)
        parsefile, self._maxfin = cls._parsefile(parseobj)
        self._init_common = _init_common
        self._maxcount = _maxcount
        return self._parse(parsefile)

    def __init__(self, *args, **kw):
        return

    def _parse(self, fileobj):
        for i in range(self._maxcount):
            if fileobj.tell() > self._maxfin - self._tp.ALIGNMENT:
                break
            if self._init_common:
                obj = self._tp(fileobj, init_common=self._init_common)
            else:
                obj = self._tp(fileobj)
            self.append(obj)
        return self

class UTF16String(Structure): # str
    def _parse(self, fileobj):
        print(f"{self._maxfin=}, {fileobj.tell()=}")
        rd = fileobj.read(self._maxfin - fileobj.tell())
        return rd.decode('UTF-16')

class UnknownPayload(Structure): # bytes
    def _parse(self, fileobj):
        return fileobj.read(self._maxfin - fileobj.tell())
