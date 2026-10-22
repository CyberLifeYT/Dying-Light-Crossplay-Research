#!/usr/bin/env python3
"""
dl_xbox_dns_phased.py — Phase-marked DNS observation of the Xbox console.

WHY A PHASED VERSION
--------------------
The first observation run was a goldmine:

    EPIC  api.epicgames.dev
    EPIC  signaling-service-prod.euw1.live.rtcp.on.epicgames.com
    TECH  pls.dyinglightgame.com
    XBOX  sessiondirectory.xboxlive.com

But it is impossible to tell which of those came from the DYING LIGHT GAME
and which from the XBOX OS / dashboard / Game Pass app. The Xbox OS resolves
xboxlive.com constantly; a title-signed-in session resolves api.epicgames.dev
and the EOS RTC signaling host.

The only way to attribute traffic correctly is to mark phases while you
watch. This tool prints a phase banner and timestamps every query, so the
game's traffic can be isolated by phase.

PHASES (press Enter in the console when each phase starts)
    0  baseline  - console on the dashboard, DL1 NOT running
    1  game      - DL1 launched, sitting in the main menu
    2  menu      - opened the ONLINE / MATCHMAKING menus
    3  host      - created a co-op session (hosting)
    4  join      - joined a friend's co-op session
    5  play      - actually in gameplay with a friend

Every query is tagged with the current phase, so the analysis is trivial:
"which names appear in phase 3/4/5 that did NOT appear in phase 0?" —
those are the game's.

Run as Administrator (port 53):
    python dl_xbox_dns_phased.py --log xbox_phased.log
"""
import argparse
import ctypes
import datetime
import os
import socket
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dl_xbox_dns as D

PHASES = [
    "0-baseline: dashboard only, DL1 NOT running",
    "1-game: DL1 launched, main menu",
    "2-menu: ONLINE / MATCHMAKING menu open",
    "3-host: co-op session created (hosting)",
    "4-join: joined a friend's session",
    "5-play: in gameplay with a friend",
]


def is_admin():
    if os.name != "nt":
        return os.geteuid() == 0
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def lan_ips():
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress "
             "-notlike '127.*' -and $_.IPAddress -notlike '169.254*' } | "
             "Select-Object -ExpandProperty IPAddress"],
            capture_output=True, text=True, timeout=20)
        return [x.strip() for x in res.stdout.split() if x.strip()]
    except Exception:
        return []


class Phased(D.Obs):
    def __init__(self, logpath, upstream_dns):
        self.ph = 0
        super().__init__(logpath, upstream_dns)

    def record(self, client, proto, qname, qtype, verdict):
        cls = D.classify(qname)
        with self.lock:
            self.total += 1
            self.counts[cls] = self.counts.get(cls, 0) + 1
            self.names.add(qname.lower())
            self.fh.write("%s\tPH%d\t%s\t%s\t%s\t%d\t%s\t%s\n" % (
                datetime.datetime.now().isoformat(timespec="milliseconds"),
                self.ph, client, proto, qname, qtype, cls, verdict))


def main():
    ap = argparse.ArgumentParser(description="Phase-marked Xbox DNS observation")
    ap.add_argument("--port", type=int, default=53)
    ap.add_argument("--upstream", default="1.1.1.1")
    ap.add_argument("--log", default="xbox_phased.log")
    args = ap.parse_args()

    if args.port == 53 and not is_admin():
        print("[!] Port 53 needs Administrator. Re-launching elevated...")
        if D.relaunch_elevated([a for a in sys.argv[1:]]):
            return 0
        print("[-] Run from an Administrator cmd.exe instead.")
        return 1

    D.add_firewall_rule(args.port)

    print("=" * 76)
    print("Dying Light crossplay — PHASE-MARKED Xbox DNS observation")
    print("=" * 76)
    print("port    : %d (UDP+TCP)" % args.port)
    print("log     : %s" % args.log)
    ips = lan_ips()
    print("LAN IPs : %s" % ", ".join(ips))
    print()
    print(">>> ON THE CONSOLE: Settings -> Network -> Advanced -> DNS -> Manual")
    for ip in ips:
        print("        enter: %s" % ip)
    print()
    for i, p in enumerate(PHASES):
        print("  phase %d : %s" % (i, p))
    print()
    print("As you perform each phase, come back here and press ENTER to advance.")
    print("Ctrl+C to stop and write the summary.")
    print()

    obs = Phased(args.log, args.upstream)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    print("[+] UDP/%d listening" % args.port)

    def responder(reply, _client, _s=sock):
        try:
            _s.sendto(reply, _client)
        except Exception:
            pass

    def udp_loop():
        while True:
            try:
                data, client = sock.recvfrom(4096)
            except OSError:
                break
            D.handle_query(obs, data, client, "UDP", responder)

    t = threading.Thread(target=udp_loop, daemon=True)
    t.start()

    phase = 0
    obs.ph = 0
    print("\n>>> PHASE 0 STARTED: %s" % PHASES[0])
    try:
        while True:
            advanced = False
            try:
                if sys.stdin is not None and sys.stdin.isatty():
                    input("")
                    advanced = True
                else:
                    # no usable stdin (background launch): keep capturing,
                    # never advance a phase, never exit.
                    time.sleep(1.0)
            except EOFError:
                # stdin closed: keep the capture alive, do not advance.
                time.sleep(1.0)
            except KeyboardInterrupt:
                raise
            if not advanced:
                continue
            phase += 1
            if phase >= len(PHASES):
                print("\n[+] all phases done — Ctrl+C to finish")
                continue
            obs.ph = phase
            print("\n>>> PHASE %d STARTED: %s" % (phase, PHASES[phase]))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        obs.close()
        D.remove_firewall_rules()

    print("\n" + "=" * 76)
    print("RESULTS")
    print("=" * 76)
    # per-phase summary
    per = {}
    try:
        with open(args.log, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) < 8 or not p[1].startswith("PH"):
                    continue
                ph = p[1]
                name, cls = p[4], p[6]
                per.setdefault(ph, {}).setdefault(cls, set()).add(name)
    except OSError:
        pass
    for ph in sorted(per, key=lambda x: int(x[2:])):
        print("\n--- %s ---" % PHASES[int(ph[2:])])
        for cls in sorted(per[ph]):
            names = sorted(per[ph][cls])
            print("  [%s] %d name(s):" % (cls, len(names)))
            for n in names:
                print("      %s" % n)
    # names that appear ONLY in game phases
    base = set()
    for ph, d in per.items():
        if int(ph[2:]) == 0:
            for s in d.values():
                base |= s
    game = set()
    for ph, d in per.items():
        if int(ph[2:]) >= 1:
            for s in d.values():
                game |= s
    only = game - base
    if only:
        print("\n" + "=" * 76)
        print("*** NAMES SEEN ONLY AFTER THE GAME STARTED (game-attributable) ***")
        print("=" * 76)
        for n in sorted(only):
            print("  %s" % n)
        print("\nIf any EPIC name appears here, the DL1 XBOX BUILD USES EOS.")
        print("If sessiondirectory.xboxlive.com appears only in phases 3-5,")
        print("the game's session service is XBL, not EOS.")
    else:
        print("\n(no names appeared exclusively after the game started)")
    print("\n[+] log: %s" % os.path.abspath(args.log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
