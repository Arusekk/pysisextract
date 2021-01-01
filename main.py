
from argparse import ArgumentParser, FileType
from sisfile import SymbianFileHeader, extract_files
from e32exe import E32ImageHeader, objcopy
from util.binfile import ParseError

headers = [
    (E32ImageHeader, objcopy),
    (SymbianFileHeader, extract_files),
]

par = ArgumentParser()
par.add_argument('-f', '--format', help="Use this format and do not guess")
par.add_argument('ifile', type=FileType('rb'))
par.add_argument('target_dir')
arg = par.parse_args()

with arg.ifile as fp:
    for HeaderType, payloadfunc in headers:
        if arg.format and HeaderType.__name__ != arg.format:
            continue
        try:
            hdr = HeaderType(fp)
        except ParseError:
            if arg.format:
                raise
            fp.seek(0)
            continue
        print(hdr)
        ff = payloadfunc(fp, arg.target_dir)
        break
