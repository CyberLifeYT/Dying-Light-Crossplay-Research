#!/usr/bin/env python3
"""
dl_session_probe.py — Observe an Xbox-hosted/joined Dying Light internet
co-op session from the user's own network, WITHOUT the Xbox binary.

WHY
---
The PC build's session layer is 100% Epic Online Services (verified).
The Xbox One-lineage build's session layer is unobserved. Since the console
cannot be modified and cannot be captured at the TLS layer, the two
observable facts that decide the entire project are:

  U1  Which service does the console resolve for session discovery?
      (i.e. does it contact Microsoft, or a Techland service, or both?)
  U2  Where does the console's *gameplay* traffic actually go?
      (direct peer-to-peer UDP, or a Microsoft relay?)

If U2 shows the gameplay traffic going DIRECTLY to a peer IP:port, then a
PC-side bridge is conceivable. If it goes to a Microsoft relay over TLS, then
no PC-side component can terminate or translate the session, and the
project is infeasible without Xbox-side support.

This tool is a passive observer: it analyses a pcap you captured, or it
reads your router's connection log. It does not touch the console, does not
intercept TLS, and does not attempt to modify platform authentication.

HOW TO USE
----------
  # Option A (best): capture on the router, then triage here
  python dl_session_probe.py --pcap capture.pcap

  # Option B: from a machine on the console's LAN, watch the connection table
  python dl_session_probe.py --stats --seconds 300

  # Option C: triage a text connection log (router export)
  python dl_session_probe.py --logfile router-connections.txt

WHAT IT REPORTS
---------------
  * every remote endpoint the console contacted, classified as
    MICROSOFT / TECH / EPIC / OTHER, with port and byte counts
  * UDP flows that look like peer-to-peer game traffic
  * whether anything in the capture resembles the Chrome Engine "WD6C"
    discovery framing (it will not — the Xbox build predates it, but a
    *different* CE magic is possible and worth spotting)
"""
import argparse
import binascii
import collections
import ipaddress
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcapread import (LINKTYPE_ETHERNET, LINKTYPE_LINUX_SLL, LINKTYPE_NULL,
                      LINKTYPE_RAW)

# Well-known service ranges/names for classification.
MS_RANGES = [
    ("13.107.", "Microsoft (Azure)"),
    ("20.190.", "Microsoft (Azure)"),
    ("20.236.", "Microsoft (Azure)"),
    ("40.74.", "Microsoft (Azure)"),
    ("40.112.", "Microsoft (Azure)"),
    ("52.96.", "Microsoft (Azure)"),
    ("52.112.", "Microsoft (Azure)"),
    ("52.125.", "Microsoft (Azure)"),
    ("65.52.", "Microsoft (Azure)"),
    ("104.43.", "Microsoft (Azure)"),
    ("137.116.", "Microsoft (Xbox)"),
    ("204.79.", "Microsoft (Bing)"),
    ("23.4.", "Microsoft/Akamai"),
    ("23.20.", "Microsoft/Akamai"),
    ("23.96.", "Microsoft/Akamai"),
]
EPIC_HINTS = ("epicgames", "epicgames.dev", "epicgames.com")

GAMEISH_PORTS = {
    3074: "Xbox Live / Game Session", 3659: "Xbox Live (alt)",
    5222: "Xbox Live / STUN-ish", 5223: "Xbox Live (alt)",
    19132: "Source Query", 27015: "Steam Query",
    27016: "Steam Game", 27017: "Steam SteamDatagram",
    3074: "Xbox Live", 25565: "Source Game",
    26100: "DL game port (PC build)", 26101: "DL discovery (PC build)",
    10000: "?", 3659: "Xbox Live (alt)",
}

CE_MAGICS = {
    0x43364457: '"WD6C" (Chrome Engine 6 LAN magic, PC build only)',
    0x65707954: '"Type" literal',
    0xfb17484f: '"GameId" hash',
}


def classify_ip(ip):
    for pfx, label in MS_RANGES:
        if ip.startswith(pfx):
            return label
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return "LAN/private"
    except ValueError:
        pass
    return "OTHER"


def tcp_udp_ports(p):
    if p in GAMEISH_PORTS:
        return GAMEISH_PORTS[p]
    return ""


def analyze_pcap(path):
    import pcapread
    fmt, frames = pcapread.read_any(path)
    if fmt == "unknown":
        print("Unrecognised capture format. Convert first:")
        print("    pktmon etl2pcap trace.etl --out trace.pcapng")
        return
    print("capture: format=%s frames=%d" % (fmt, len(frames)))
    if fmt == "pcapng":
        print("(pktmon etl2pcap output — supported)")

    flows = collections.Counter()
    bytes_by_ip = collections.Counter()
    pkts_by_ip = collections.Counter()
    magics = collections.Counter()
    linktypes = collections.Counter()

    for linktype, pkt in frames:
        linktypes[linktype] += 1
        ip_off = None
        if linktype == LINKTYPE_ETHERNET:
            if len(pkt) < 34 or pkt[12:14] != b"\x08\x00":
                continue
            ip_off = 14
        elif linktype == LINKTYPE_RAW:
            if len(pkt) < 20 or (pkt[0] >> 4) != 4:
                continue
            ip_off = 0
        elif linktype == LINKTYPE_LINUX_SLL:
            if len(pkt) < 24:
                continue
            ip_off = 16
        elif linktype == LINKTYPE_NULL:
            if len(pkt) < 4:
                continue
            if (pkt[0] >> 4) != 4:
                continue
            ip_off = 4
        else:
            continue
        if len(pkt) < ip_off + 20:
            continue
        if (pkt[ip_off] >> 4) != 4:
            continue
        ihl = (pkt[ip_off] & 0x0F) * 4
        proto = pkt[ip_off + 9]
        src = ".".join(str(b) for b in pkt[ip_off + 12:ip_off + 16])
        dst = ".".join(str(b) for b in pkt[ip_off + 16:ip_off + 20])
        payload = b""
        sp = dp = 0
        if proto == 17 and len(pkt) >= ip_off + ihl + 8:
            u = ip_off + ihl
            sp, dp = struct.unpack("!HH", pkt[u:u + 4])
            payload = pkt[u + 8:]
        elif proto == 6 and len(pkt) >= ip_off + ihl + 4:
            u = ip_off + ihl
            sp, dp = struct.unpack("!HH", pkt[u:u + 4])
            doff = (pkt[u + 12] >> 4) * 4
            payload = pkt[u + doff:]
        else:
            continue
        flows[(src, sp, dst, dp, proto)] += 1
        pkts_by_ip[dst] += 1
        bytes_by_ip[dst] += len(pkt)
        for mg, desc in CE_MAGICS.items():
            if struct.pack("<I", mg) in payload[:16] or struct.pack(">I", mg) in payload[:16]:
                magics[desc] += 1

    print("linktypes seen: %s" % dict(linktypes))
    print()
    print("=" * 78)
    print("REMOTE ENDPOINTS (by destination)")
    print("=" * 78)
    print("%-16s %-10s %8s %10s  %s" % ("IP", "CLASS", "PKTS", "BYTES", "PORTS"))
    for ip, c in pkts_by_ip.most_common(30):
        ports = sorted({f[3] for f in flows if f[2] == ip})
        print("%-16s %-10s %8d %10d  %s" % (ip, classify_ip(ip), c, bytes_by_ip[ip],
                                            ",".join("%d%s" % (p, tcp_udp_ports(p) and " (%s)" % tcp_udp_ports(p) or "") for p in ports[:6])))
    print()
    print("=" * 78)
    print("TOP FLOWS")
    print("=" * 78)
    for (src, sp, dst, dp, proto), c in flows.most_common(25):
        print("  %6d  %s:%d -> %s:%d  proto=%s  %s" % (c, src, sp, dst, dp,
                                                       "UDP" if proto == 17 else "TCP",
                                                       tcp_udp_ports(dp) or tcp_udp_ports(sp)))
    if magics:
        print("\nChrome Engine magics seen:", dict(magics))


def analyze_logfile(path):
    """
    Parse a router/console connection log.

    Handles the common shapes:
      "1.2.3.4:5678 -> 9.9.9.9:443"
      "src=1.2.3.4 dst=9.9.9.9 dport=443 proto=TCP"
      "1.2.3.4  9.9.9.9  443  TCP  1234"
    The remote endpoint is the last IP on the line that is directly followed
    by a port number.
    """
    ip_re = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ips = ip_re.findall(line)
            if not ips:
                continue
            proto = ""
            m = re.search(r"\b(TCP|UDP|ICMP|IGMP)\b", line, re.I)
            if m:
                proto = m.group(1).upper()
            rows.append((line, ips, proto))
    if not rows:
        print("no IP-bearing lines found in %s" % path)
        return
    print("parsed %d lines with IP addresses" % len(rows))

    counts = collections.Counter()
    protos = collections.Counter()
    for line, ips, proto in rows:
        remote, port = None, None
        for ip in reversed(ips):
            idx = line.rfind(ip)
            tail = line[idx + len(ip):]
            pm = re.match(r"[:\s.]+(\d{1,5})(?![0-9])", tail)
            if pm:
                cand = int(pm.group(1))
                if 0 < cand < 65536:
                    remote, port = ip, cand
                    break
        if remote is None:
            remote = ips[-1]
        if port is None:
            # look for an explicit dport=/port= token anywhere on the line
            dp = re.search(r"\b(?:dport|dest_?port|remote_?port|port)\s*[=:]\s*(\d{1,5})",
                           line, re.I)
            if dp:
                cand = int(dp.group(1))
                if 0 < cand < 65536:
                    port = cand
        try:
            if ipaddress.ip_address(remote).is_private:
                continue
        except ValueError:
            continue
        counts[(remote, port or 0)] += 1
        if proto:
            protos[proto] += 1

    print("=" * 78)
    print("%-16s %-10s %8s  %s" % ("REMOTE IP", "CLASS", "COUNT", "PORT"))
    for (ip, port), c in counts.most_common(40):
        print("%-16s %-10s %8d  %d %s" % (ip, classify_ip(ip), c, port,
                                           tcp_udp_ports(port)))
    if protos:
        print("\nprotocol mentions: %s" % dict(protos))
    print("\nsample raw lines (sanity check the parse):")
    for line, ips, proto in rows[:8]:
        print("   %s" % line[:150])


def analyze_stats(seconds):
    import subprocess
    import time
    seen = {}
    end = time.time() + seconds
    print("[+] polling the connection table for %ds" % seconds)
    print("    (run this ON A MACHINE ON THE CONSOLE'S LAN, while the console")
    print("     is in an active co-op session)")
    while time.time() < end:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
        except Exception as e:
            print("netstat failed:", e)
            return
        for line in out.splitlines():
            p = line.split()
            if len(p) < 4 or p[0].lower() not in ("tcp", "udp"):
                continue
            def split_addr(s):
                s = s.strip()
                if ":" not in s:
                    return s, 0
                h, _, pt = s.rpartition(":")
                try:
                    return h, int(pt)
                except ValueError:
                    return h, 0
            lh, lp = split_addr(p[1])
            rh, rp = split_addr(p[2])
            try:
                if ipaddress.ip_address(rh).is_private:
                    continue
            except ValueError:
                continue
            key = (rh, rp, p[0])
            seen[key] = seen.get(key, 0) + 1
        time.sleep(1.0)
    print("\n%-16s %-10s %8s  %s" % ("REMOTE IP", "CLASS", "SEEN", "PROTO/PORT"))
    for (ip, port, proto), c in sorted(seen.items(), key=lambda kv: -kv[1]):
        print("%-16s %-10s %8d  %s/%d %s" % (ip, classify_ip(ip), c, proto, port, tcp_udp_ports(port)))


def main():
    ap = argparse.ArgumentParser(description="Observe an Xbox Dying Light internet session")
    ap.add_argument("--pcap", default="")
    ap.add_argument("--logfile", default="")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--seconds", type=int, default=300)
    args = ap.parse_args()
    if args.pcap:
        analyze_pcap(args.pcap)
    elif args.logfile:
        analyze_logfile(args.logfile)
    elif args.stats:
        analyze_stats(args.seconds)
    else:
        print("need one of --pcap / --logfile / --stats")
        return 2

    print()
    print("=" * 78)
    print("HOW TO READ THIS")
    print("=" * 78)
    print("  Q1  Does the console talk to MICROSOFT-labelled IPs on Xbox Live")
    print("      ports (3074/3659/5222/5223)?")
    print("        YES -> the console's session service is Microsoft-operated.")
    print("              A PC client cannot participate without an Xbox Live")
    print("              identity and a Microsoft-issued session token.")
    print("        NO  and you see a TECH-labelled IP instead")
    print("              -> a Techland service is in the path. That would be a")
    print("                 candidate shared meeting point worth a deep dive.")
    print()
    print("  Q2  Is there a high-volume UDP flow to a NON-MICROSOFT IP?")
    print("        YES -> gameplay is peer-to-peer; a PC-side bridge is")
    print("               conceivable (you would still need to match the")
    print("               replication protocol).")
    print("        NO  -> gameplay is relayed by Microsoft over TLS; no PC-side")
    print("               component can terminate or translate the session.")
    print("               THAT IS THE FEASIBILITY KILLER.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
