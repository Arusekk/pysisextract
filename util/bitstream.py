class Bits:
    __slots__ = '_nbit', '_bits', '_byte'
    little = True

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
            except IndexError:
                return
            self._nbit = 7
        else:
            self._nbit -= 1
        if self.little:
            return (self._byte >> (7 - self._nbit)) & 1
        else:
            return (self._byte >> self._nbit) & 1

    def nextbits(self, n, little=None):
        if little is None:
            little = self.little
        acc = 0
        if little:
            for _ in range(n):
                acc <<= 1
                acc |= self.nextbit()
        else:
            for i in range(n):
                acc |= self.nextbit() << i
        return acc

    def iterbits(self):
        while True:
            if self._nbit == 0:
                try:
                    self._byte = self._bits.pop(0)
                except IndexError:
                    return
                self._nbit = 7
            else:
                self._nbit -= 1
            if self.little:
                yield (self._byte >> (7 - self._nbit)) & 1
            else:
                yield (self._byte >> self._nbit) & 1


class Decompressor(Bits):
    __slots__ = '_acc', '_decoding'

    def __init__(self):
        super().__init__()
        self._acc = 1

    def nextunit(self, mapping=None):
        if mapping is None:
            mapping = self._decoding
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

    def iterunits(self):
        for b in self.iterbits():
            acc = self._acc = (self._acc << 1) | b
            try:
                m = self._decoding[acc]
            except (KeyError, IndexError):
                if acc > max(self._decoding):
                    raise
                continue
            self._acc = 1
            yield m
