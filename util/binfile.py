
import zlib
from enum import Enum, EnumMeta
from io import BytesIO
from struct import Struct

def TellFile(fp):
    return fp

class StructurePayloadLength:
    pass

class StructureSubClass:
    pass

class StructureAnnotations(dict):
    def __init__(self, pardict):
        self.pardict = pardict
        super().__init__()
    def __setitem__(self, key, val):
        if key in self:
            self.pardict['_offsets'] = {}
            return
        return super().__setitem__(key, val)

class ParseError(ValueError):
    pass

class StructureMeta(type):
    @classmethod
    def __prepare__(meta, name, bases):
        d = {}
        d.update({
            '__annotations__': StructureAnnotations(d),
            '_subclassfield': None,
            '_offsets': {},
        })
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
        dic['_struct'] = struc
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
            if isinstance(value, type):
                del template[idx]
                setattr(cls, pattern, value)
            else:
                template[template.index(pattern)] = value
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
        return cls._struct.unpack(parsefile.read(cls._struct.size))

    @staticmethod
    def _parsefile(parseobj):
        if hasattr(parseobj, 'read'):
            return TellFile(parseobj)
        return BytesIO(parseobj)

    @classmethod
    def __new__(cls, subcl, parseobj=None, parsefile=None):
        if cls._template:
            raise TemplateNeeded()
        if isinstance(parseobj, Structure):
            self = super().__new__(subcl)
            self.__dict__.update(parseobj.__dict__)
        else:
            parsefile = cls._parsefile(parseobj)
            self = super().__new__(subcl)
        if parseobj is None:
            return self
        offset = parsefile.tell()
        if offset % cls.ALIGNMENT:
            padding = parsefile.read(-offset % cls.ALIGNMENT)
            if any(padding):
                raise ParseError(f"nonzero padding at offset {offset}")
        if hasattr(cls, '_struct'):
            vals = cls._readstruct(parsefile)
            if cls._named:
                namemap = cls._named(*vals)._asdict()
            else:
                namemap = dict(enumerate(vals))
            self.__dict__.update(namemap)
        retype = False
        for field, tp in cls.__annotations_all__.items():
            if field in self.__dict__:
                continue
            try:
                val = tp(parsefile)
            except ValueError:
                raise ParseError(f"{subcl.__name__} at offset {offset}: "
                                 f"invalid {tp.__name__} {field}")
            try:
                defval = getattr(cls, field)
            except AttributeError:
                pass
            else:
                if defval != val:
                    raise ParseError(f"{parseobj} at offset {offset}: "
                                     f"expected {defval}, found {val}")
            if field == self._subclassfield:
                name = val.name
                try:
                    retype = next(c for c in cls.get_subclasses()
                                    if c.__name__ == name)
                except StopIteration:
                    raise RuntimeError(f"subclass {name} not found")
            setattr(self, field, val)
        if retype and not issubclass(subcl, retype):
            return retype(self, parsefile=parsefile)
        print(f"Parsed: {self!r}")
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
        return f"""<{self.__class__.__name__}:  {", ".join(f"{key}={value!r}" for key, value in self._fields())}>"""

def get_base_type(tp, metaclass=StructureMeta):
    class BaseType(tp, Structure, metaclass=metaclass):
        @classmethod
        def __new__(cls, subcl, parseobj):
            if isinstance(parseobj, tp):
                val = parseobj
            else:
                parsefile = cls._parsefile(parseobj)
                val, = cls._readstruct(parsefile)
            self = tp.__new__(subcl, val)
            print(f"Parsed: {self!r}")
            return self
        def __repr__(self):
            return f"<{type(self).__name__}: {super().__repr__()}>"
    return BaseType

BaseType = get_base_type(int)

Int32 = StructureMeta.from_struct('i', name='Int32', bases=BaseType)
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
    def _struc(self):
        return Struct('I' if self < 0x80000000 else 'Q')

class ZlibReader:
    def __init__(self, fp):
        self._fp = fp
        self._obj = zlib.decompressobj()
        self._off = 0
        self._readbuf = BytesIO()

    def tell(self):
        return self._off

    def read(self, n):
        if n < 0:
            raise ValueError("No reading everything!!!")
        ret = self._readbuf.read(n)
        while len(ret) < n:
            ret += self._obj.decompress(self._fp.read(1))
        self._readbuf = BytesIO(ret[n:])
        ret = ret[:n]
        self._off += len(ret)
        return ret

class Zlib(Structure):
    _template = '_tp',
    @classmethod
    def __new__(cls, subcl, parseobj):
        if cls._template:
            raise TemplateNeeded()
        parsefile = cls._parsefile(parseobj)
        return cls._tp(ZlibReader(parseobj))
