class Bits:
    __slots__ = '_nbit', '_bits', '_byte'
    def __init__(self):
        self._nbit = 0
        self._byte = 0
        self._bits = bytearray()
    def feed(self, data):
        self._bits += data
    def __iter__(self):
        return self.iterbits()
    def nextbit(self):
        if self._nbit == 0:
            try:
                self._byte = self._bits.pop(0)
            except IndexError as e:
                return
            self._nbit = 7
        else:
            self._byte >>= 1
            self._nbit -= 1
        return self._byte & 1
    def iterbits(self):
        while True:
            if self._nbit == 0:
                try:
                    self._byte = self._bits.pop(0)
                except IndexError as e:
                    return
                self._nbit = 7
            else:
                self._byte >>= 1
                self._nbit -= 1
            yield self._byte & 1


class Decompressor(Bits):
    __slots__ = '_acc',
    def __init__(self):
        super().__init__()
        self._acc = 1
    def nextunit(self, mapping):
        maxacc = max(mapping)
        for b in self.iterbits():
            acc = self._acc = (self._acc << 1) | b
            try:
                m = mapping[acc]
            except (KeyError, IndexError):
                if acc > maxacc:
                    raise
                continue
            self._acc = 1
            return m
    def iterunits(self, mapping):
        maxacc = max(mapping)
        for b in self.iterbits():
            acc = self._acc = (self._acc << 1) | b
            try:
                m = mapping[acc]
            except (KeyError, IndexError):
                if acc > maxacc:
                    raise
                continue
            self._acc = 1
            yield m
