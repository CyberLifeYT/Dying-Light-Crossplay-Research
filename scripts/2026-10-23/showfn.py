"""Print selected function blocks from an XrefDecomp output file, stripping log boilerplate.
usage: python showfn.py <file> <hexaddr> [<hexaddr> ...]   (use 'all-headers' to list headers only)"""
import re, sys

path, wanted = sys.argv[1], [a.lower() for a in sys.argv[2:]]
blocks, cur = {}, None
for line in open(path, encoding="utf-8", errors="replace"):
    m = re.match(r"//==== FUNC ([0-9a-f]+) ", line)
    if m:
        cur = m.group(1)
        blocks[cur] = []
    if cur:
        blocks[cur].append(line.rstrip("\n"))

NOISE = re.compile(r"^\s*(local_[0-9a-f]+(\[0\])? = |undefined\d? local_|char \*local_|void \*local_|"
                   r"undefined8 local_|undefined4 local_|undefined1 local_|free\(local_|"
                   r"(TVar\d|pSVar\d|this) = Log::Settings|if \(4 < \(int\)TVar)")
for a in wanted:
    if a == "all-headers":
        for b in blocks.values():
            print(b[0])
        continue
    for line in blocks.get(a, [f"// {a} not in file"]):
        if not NOISE.match(line):
            print(line)
    print()
