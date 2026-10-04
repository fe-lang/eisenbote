#!/usr/bin/env python3
"""Write the crier-bin input stream for a fragment directory in os.listdir
order (the order towncrier sees), optionally followed by a changelog."""
import os
import sys

out = sys.stdout.buffer
directory = sys.argv[1]
for name in os.listdir(directory):
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        continue
    data = open(path, "rb").read()
    out.write(b"F %d %s\n" % (len(data), name.encode()))
    out.write(data)
if len(sys.argv) > 2 and os.path.isfile(sys.argv[2]):
    data = open(sys.argv[2], "rb").read()
    out.write(b"C %d\n" % len(data))
    out.write(data)
