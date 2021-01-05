
import argparse
import json
from os.path import basename
from e32exe import mangle

par = argparse.ArgumentParser(description="""
Example usage:
gen-e32def.py [--clean] $(find ~/symbian -name '*.def'|grep -v test|grep -i /eabi/)
""")
par.add_argument('infile', nargs='+')
par.add_argument('--clean', action='store_true', help="throw away current def")

arg = par.parse_args()

if arg.clean:
    deffiles = {}
else:
    try:
        from e32def import deffiles
    except ImportError:
        deffiles = {}

for fn in arg.infile:
    d = {}
    dllname = basename(fn).split('.')[0].lower()
    with open(fn) as f:
        for line in f:
            fields = line.strip().split('@')
            if len(fields) >= 2:
                sym, num = fields
                num = num.split()[0]
                d[int(num)] = sym.strip()
    if not d:
        print(f"empty: {fn}")
    deffiles[dllname] = [d.get(i, f'_{mangle(dllname)}_missing_{i}')
                         for i in range(max(d, default=0) + 1)]

with open('e32def.py', 'w') as fp:
    fp.write('deffiles = ')
    json.dump(deffiles, fp, indent=4)
