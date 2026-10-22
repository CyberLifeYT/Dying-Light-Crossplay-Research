#!/usr/bin/env python3
"""
dl_probe_techland.py — Probe the legacy Techland master servers that the
pre-EOS Dying Light 1 PC build used, to see whether they are still alive and
what they speak.

WHY THIS MATTERS
----------------
`data/network.scr` in the shipped PC build still contains:

    AuthorizationServer("AuthServer.techland.pl")
    AuthorizationServer("AuthServer1.techland.pl") ... ("AuthServer9...")
    GameListServer("GameListServer.techland.pl")
    GamePort(26100)
    AllSeeingEyePort(1)        -> discovery port = GamePort + 1 = 26101

Those hostnames STILL RESOLVE (to live AWS addresses), even though the
2022 EOS build no longer references them in code. The 2016-era Xbox One
build plausibly still talks to exactly this class of service.

If the Techland master/auth service is still up and still speaks the legacy
protocol, then it is the single most promising meeting point between the
PC and Xbox builds: a *shared vendor-operated service* rather than two
disjoint platform backends (Epic vs Microsoft).

This tool probes, read-only:
  * TCP connect + banner grab on the legacy ports
  * UDP "All-Seeing-Eye" style discovery on the AllSeeingEye port
  * whether the host answers HTTP/HTTPS at all

It sends only well-formed, benign queries. It does not attempt to
authenticate, brute-force, or bypass anything.
"""
import argparse
import binascii
import socket
import struct
import sys
import time

LEGACY_TCP_PORTS = [80, 443, 27000, 27001, 27002, 27015, 27016, 27017,
                     27018, 27019, 27020, 27021, 27022, 27023, 27024, 27025,
                     26100, 26101, 29900, 29901, 3074, 5222, 5223, 3659]
LEGACY_UDP_PORTS = [26100, 26101, 27015, 27016, 27017, 27018, 27019]


def tcp_probe(host, port, timeout=2.5, grab=True):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except Exception as e:
        return None, str(e)
    banner = b""
    if grab:
        s.settimeout(timeout)
        try:
            s.sendall(b"\n")
            banner = s.recv(512)
        except Exception:
            banner = b"<no banner>"
    s.close()
    return True, banner


def udp_probe(host, port, payload=b"\n", timeout=1.5, count=3):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
    except Exception as e:
        return []
    got = []
    for _ in range(count):
        try:
            s.sendto(payload, (host, port))
            data, addr = s.recvfrom(4096)
            got.append((addr, data))
        except socket.timeout:
            break
        except Exception:
            break
    s.close()
    return got


def http_probe(host, port, path="/", tls=False):
    try:
        s = socket.create_connection((host, port), timeout=3)
    except Exception as e:
        return "connect-fail: %s" % e
    req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: probe\r\n"
           "Connection: close\r\n\r\n" % (path, host)).encode()
    try:
        s.sendall(req)
        s.settimeout(4)
        data = s.recv(1024)
    except Exception as e:
        data = b"<recv-fail %s>" % str(e).encode()
    s.close()
    return data.split(b"\r\n")[0].decode("latin1", "replace")


def main():
    ap = argparse.ArgumentParser(description="Probe legacy Techland master servers")
    ap.add_argument("--host", action="append", default=[],
                    help="host to probe (default: the legacy names)")
    ap.add_argument("--tcp-ports", default="")
    ap.add_argument("--udp-ports", default="")
    ap.add_argument("--http", action="store_true", help="also do an HTTP GET on 80/443")
    args = ap.parse_args()

    hosts = args.host or ["authserver.techland.pl", "authserver1.techland.pl",
                           "gamelistserver.techland.pl", "authserver2.techland.pl"]
    tcp_ports = ([int(p) for p in args.tcp_ports.split(",")] if args.tcp_ports
                 else LEGACY_TCP_PORTS)
    udp_ports = ([int(p) for p in args.udp_ports.split(",")] if args.udp_ports
                 else LEGACY_UDP_PORTS)

    for host in hosts:
        try:
            ip = socket.gethostbyname(host)
        except Exception as e:
            print("== %s : resolve failed (%s)" % (host, e))
            continue
        print("=" * 74)
        print("== %s (%s)" % (host, ip))
        print("=" * 74)

        opened = []
        for p in tcp_ports:
            ok, info = tcp_probe(ip, p)
            if ok:
                opened.append(p)
                print("  TCP/%-5d OPEN   banner=%r" % (p, info[:120]))
        if not opened:
            print("  no TCP ports open in the probed set")

        for p in udp_ports:
            got = udp_probe(ip, p)
            if got:
                for addr, data in got:
                    print("  UDP/%-5d REPLY from %s len=%d %r"
                          % (p, addr, len(data), data[:64]))
        if args.http:
            for p in (80, 443):
                if p in opened:
                    print("  HTTP  %s:%d -> %s" % (host, p, http_probe(ip, p)))
        print()

    print("=" * 74)
    print("INTERPRETATION")
    print("=" * 74)
    print("  * Open TCP ports with a recognisable banner on the legacy")
    print("    AuthServer/GameListServer hosts  => the pre-EOS Techland")
    print("    backend is STILL RUNNING. That makes it the only candidate")
    print("    service that BOTH a 2016-era Xbox build and a re-pointed PC")
    print("    build could speak. Next step would be to capture the")
    print("    protocol from a real 2016/2017 PC client.")
    print("  * Everything closed / no banner  => the legacy backend is gone")
    print("    and there is NO shared vendor service. The only remaining")
    print("    meeting points are (a) the Xbox console itself, or (b) a")
    print("    full PC-side re-implementation of the Xbox session service.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
