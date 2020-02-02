#!/usr/bin/env python3
import sys
import os
from textwrap import dedent
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_PATH)
import resguard
from subprocess import check_output

branch = check_output(f"git -C {BASE_PATH} rev-parse --abbrev-ref HEAD", shell=True, universal_newlines=True).rsplit()


print("[![Build Status](https://travis-ci.org/dhilst/resguard.svg?branch={branch})](https://travis-ci.org/dhilst/resguard)")
print(resguard.__doc__)
print()
for func in 'parse_dc create_base unpack_union Dataclass'.split():
    print(f"# {func}")
    dcstr = getattr(resguard, func).__doc__
    print(dedent(dcstr))
