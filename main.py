
from argparse import ArgumentParser, FileType
from sisfile import SymbianFileHeader, SISField

par = ArgumentParser()
par.add_argument('ifile', type=FileType('rb'))
arg = par.parse_args()
with arg.ifile as fp:
    hdr = SymbianFileHeader(fp)
    print(hdr)
    ff = SISField(fp)
    print(ff)
