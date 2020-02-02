#!/usr/bin/env python3
import sys
import os
from textwrap import dedent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import resguard

print(resguard.__doc__)
print()
for func in 'parse_dc create_base unpack_union Dataclass'.split():
    print(f"# {func}")
    dcstr = getattr(resguard, func).__doc__
    print(dedent(dcstr))
