#!/bin/sh
python3 gen-e32def.py $(find /mnt/dane/Dane/gicior/SymbianSource -iname '*.def' |grep -vi test |grep -i /eabi/)
