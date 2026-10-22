#!/usr/bin/env python3
"""
dl_phase_report.py — Analyse a phase-marked Xbox DNS log and attribute
traffic to the game vs the Xbox OS.

This is the analysis half of dl_xbox_dns_phased.py, usable standalone on any
log produced by it (or by hand).

IT ANSWERS THE DECISIVE QUESTION:
    Which hostnames does the DYING LIGHT XBOX BUILD resolve, as opposed to
    the Xbox dashboard / OS?

Method: names that appear ONLY in phases >= 1 (i.e. after the game started)
cannot have come from the console's idle OS chatter.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dl_xbox_dns import classify


def load(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 8:
                continue
            if not p[1].startswith("PH"):
                continue
            rows.append({"ts": p[0], "ph": int(p[1][2:]), "client": p[2],
                         "proto": p[3], "name": p[4].rstrip("."),
                         "qtype": p[5], "cls": p[6], "res": p[7]})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Analyse a phase-marked Xbox DNS log")
    ap.add_argument("log", nargs="?", default="xbox_phased.log")
    args = ap.parse_args()
    rows = load(args.log)
    if not rows:
        print("no phase-marked rows in %s" % args.log)
        return 1

    per = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        per[r["ph"]][r["cls"]].add(r["name"])

    print("=" * 78)
    print("PER-PHASE HOSTNAMES")
    print("=" * 78)
    for ph in sorted(per):
        print("\n--- PHASE %d (%d unique names) ---" % (ph, len({n for s in per[ph].values() for n in s})))
        for cls in sorted(per[ph]):
            print("  [%-8s] %s" % (cls, ", ".join(sorted(per[ph][cls]))))

    base = set()
    for s in per.get(0, {}).values():
        base |= s
    game = set()
    for ph, d in per.items():
        if ph >= 1:
            for s in d.values():
                game |= s
    only = game - base

    print("\n" + "=" * 78)
    print("GAME-ATTRIBUTABLE HOSTNAMES (seen only after the game started)")
    print("=" * 78)
    if not only:
        print("  (none - every name also appeared in the baseline phase)")
        print("  => The game's traffic is indistinguishable from the OS's,")
        print("     OR the game was already running during phase 0.")
    for n in sorted(only):
        print("  %-8s %s" % (classify(n), n))

    print("\n" + "=" * 78)
    print("INTERPRETATION")
    print("=" * 78)
    ep = sorted(n for n in only if classify(n) == "EPIC")
    tech = sorted(n for n in only if classify(n) == "TECH")
    xbl = sorted(n for n in only if classify(n) == "XBOX")
    if ep:
        print("  The DL1 XBOX BUILD RESOLVES EPIC SERVICES:")
        for n in ep:
            print("     %s" % n)
        print("  => The console build uses Epic Online Services.")
        print("     If it uses EOS Lobby + EOS P2P, then PC and Xbox are on the")
        print("     SAME platform, and crossplay is blocked only by:")
        print("       (a) product/sandbox separation, (b) PlatformId filtering,")
        print("       (c) the Net::Repl version/content difference.")
        print("     That is a *tractable* engineering problem, not a dead end.")
    if tech:
        print("\n  The game also touches a Techland service:")
        for n in tech:
            print("     %s" % n)
    if xbl:
        print("\n  Xbox-Live-only names seen only after the game started:")
        for n in xbl:
            print("     %s" % n)
        if any("sessiondirectory" in n for n in xbl):
            print("  => sessiondirectory.xboxlive.com is the XBL session service.")
            print("     If it appears only in the HOST/JOIN/PLAY phases, the game's")
            print("     matchmaking is XBL, not EOS — that decides the whole project.")

    # also show the first-seen timestamp of the interesting names
    print("\n" + "=" * 78)
    print("FIRST-SEEN TIMESTAMP OF INTERESTING NAMES")
    print("=" * 78)
    first = {}
    for r in rows:
        first.setdefault(r["name"], (r["ts"], r["ph"], r["cls"]))
    for n in sorted(first, key=lambda x: first[x][0]):
        cls = first[n][2]
        if cls in ("EPIC", "TECH") or "sessiondirectory" in n:
            print("  %-24s PH%-2d %-8s %s" % (first[n][0][11:23], first[n][1], cls, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
