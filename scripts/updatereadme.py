#!/usr/bin/env python3
import sys
import os
from inspect import signature
from textwrap import dedent
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_PATH)
import resguard
from subprocess import check_output

print("[![Build Status](https://travis-ci.org/dhilst/resguard.svg?branch=master)](https://travis-ci.org/dhilst/resguard)")
print(resguard.__doc__)
print()
for func in 'parse_dc create_base unpack_union Dataclass'.split():
    fp = getattr(resguard, func)
    dcstr = fp.__doc__
    print(f"# {func}{signature(fp)}")
    print(dedent(dcstr))
