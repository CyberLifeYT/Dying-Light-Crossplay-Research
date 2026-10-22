#!/usr/bin/env python3
"""
dl_scan_techland.py — Targeted port probe of the legacy Techland master
servers that the pre-EOS Dying Light 1 PC build used.

WHY
---
`data/network.scr` (shipped in the 2022 PC build) still lists:

    AuthorizationServer("AuthServer.techland.pl")   ... 1..9
    GameListServer("GameListServer.techland.pl")
    GamePort(26100)
    AllSeeingEyePort(1)        -> 26101

Those names STILL RESOLVE to AWS addresses, and the 2016-era Xbox One build
plausibly used the same class of Techland-operated session-listing service
(console builds of Techland titles historically shared the vendor's master
service and only swapped the platform *auth* layer).

My first scan was narrow and found nothing. This does a wider, targeted
probe (TCP connect + UDP probe) over the port ranges a session-listing
service would plausibly use.

SCOPE / ETHICS
--------------
This probes a small, explicitly-enumerated set of ports on the *game's own
historical service hosts* to answer one narrow research question: is the
pre-EOS Techland backend still running? It is not a mass scan, sends no
payloads beyond an empty/short probe, and does not attempt to authenticate
or bypass anything. If you want to be conservative, use --tcp-only with a
single host.
"""
import argparse
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Ports plausibly used by a session-listing / master service or a game host.
TCP_PORTS = [
    80, 443, 8080, 8443, 8000, 8888,
    27000, 27001, 27002, 27003, 27004, 27005, 27006, 27007, 27008, 27009,
    27010, 27011, 27012, 27013, 27014, 27015, 27016, 27017, 27018, 27019,
    27020, 27021, 27022, 27023, 27024, 27025, 27026, 27027, 27028, 27029,
    27030, 27031, 27032, 27033, 27034, 27035,
    26100, 26101, 26102, 26103,
    29900, 29901, 29902, 29903, 29904, 29905,
    3074, 3659, 5222, 5223, 14000, 11111, 11000, 12000,
    7777, 9999, 4444, 25565, 19132, 19133, 28000, 28910,
    5222, 5000, 5001, 9000, 9001, 10000, 10001,
]
UDP_PORTS = [26100, 26101, 27000, 27015, 27016, 27017, 27018, 27019, 27020,
             29900, 29901, 3074, 3659, 5222, 5223, 19132]


def tcp_one(args):
    ip, port, timeout = args
    t0 = time.time()
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.settimeout(timeout)
        banner = b""
        try:
            s.sendall(b"\n")
            banner = s.recv(256)
        except Exception:
            pass
        s.close()
        return (ip, port, True, banner, time.time() - t0)
    except Exception:
        return (ip, port, False, b"", time.time() - t0)


def udp_one(args):
    ip, port, payload, timeout = args
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(payload, (ip, port))
        data, addr = s.recvfrom(2048)
        s.close()
        return (ip, port, True, data, 0)
    except Exception:
        return (ip, port, False, b"", 0)


def main():
    ap = argparse.ArgumentParser(description="Targeted probe of legacy Techland master servers")
    ap.add_argument("--host", action="append", default=[])
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--tcp-only", action="store_true")
    ap.add_argument("--udp-only", action="store_true")
    ap.add_argument("--ports", default="", help="comma list to override TCP ports")
    ap.add_argument("--udp-payload", default="\\n")
    args = ap.parse_args()

    hosts = args.host or ["authserver.techland.pl", "gamelistserver.techland.pl",
                          "authserver1.techland.pl", "authserver2.techland.pl"]
    ips = []
    for h in hosts:
        try:
            ips.append((h, socket.gethostbyname(h)))
        except Exception as e:
            print("resolve %s failed: %s" % (h, e))
    if not ips:
        print("nothing to probe")
        return 1

    tcp_ports = ([int(p) for p in args.ports.split(",")] if args.ports else TCP_PORTS)
    payload = args.udp_payload.encode().decode("unicode_escape").encode()

    results = []
    if not args.udp_only:
        jobs = [(ip, p, args.timeout) for _, ip in ips for p in tcp_ports]
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            for r in ex.map(tcp_one, jobs):
                if r[2]:
                    results.append(r)
    if not args.tcp_only:
        jobs = [(ip, p, payload, 1.5) for _, ip in ips for p in UDP_PORTS]
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            for r in ex.map(udp_one, jobs):
                if r[2]:
                    results.append(r)

    name = {ip: h for h, ip in ips}
    print("=" * 74)
    print("RESULTS — %d open endpoint(s) of %d probed" % (len(results), len(ips) * (len(tcp_ports) + len(UDP_PORTS))))
    print("=" * 74)
    for ip, port, ok, blob, dt in sorted(results, key=lambda r: (r[0], r[1])):
        kind = "TCP" if port in tcp_ports else "UDP"
        print("  %-22s %s/%-5d  %.2fs  %r" % (name.get(ip, ip), kind, port, dt, blob[:80]))
    if not results:
        print("  (nothing open)")
    print()
    print("INTERPRETATION")
    print("  * Any open port on authserver/gamelistserver.techland.pl means the")
    print("    pre-EOS Techland session-listing service is STILL RUNNING.")
    print("    That is the single most valuable discovery available, because it")
    print("    would be a service that BOTH the 2016 Xbox build and a")
    print("    re-pointed PC build could speak — the only shared vendor")
    print("    meeting point that does not require the console to be modified.")
    print("  * Nothing open => the legacy backend is gone, and the console must")
    print("    be using either Xbox Live (Microsoft) or a still-live Techland")
    print("    host we have not identified. Next step is dl_xbox_dns.py to")
    print("    enumerate what the console actually resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
