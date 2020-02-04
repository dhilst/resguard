#!/usr/bin/env python3
import re
from io import StringIO
from subprocess import check_call
from shutil import move
with open("setup.py") as f:
    s = StringIO()
    for line in f:
        if "version=" in line:
            match = re.search(r"version=\"(?P<version>\d+\.\d+)\"", line)
            if match is not None:
                maj, min_ = match.group("version").split(".")
                version = f"{maj}.{min_}"
                new_version = f"{maj}.{int(min_) + 1}"
                line = line.replace(version, new_version)
        s.write(line)

with open("setup.py.tmp", "w") as f:
    f.write(s.getvalue())
    move("setup.py.tmp", "setup.py")

check_call("git commit -m 'Bump' setup.py", shell=True)
check_call(f"git tag v{new_version}", shell=True)
