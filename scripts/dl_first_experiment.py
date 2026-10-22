#!/usr/bin/env python3
"""
dl_first_experiment.py — One-command harness for the FIRST experiment.

WHAT IT DOES
------------
Runs the two cheapest, highest-information tests in sequence and prints a
single verdict at the end:

  TEST A  PC LAN co-op discovery, observed locally.
          Starts a UDP listener on the DL discovery port (26101) and a
          broadcaster, then (optionally) waits for you to run the game in
          LAN mode and host a session. Reports every WD6C field it decodes.

  TEST B  Xbox One reachability of the same path.
          Broadcasts a WD6C probe on the LAN and listens for replies, so you
          can tell whether the console speaks this protocol at all.

  TEST C  DNS inventory.
          Optionally points a configured DNS listener at the game and reports
          every name the game resolves (using dl_dns_logger.py).

It is deliberately READ-ONLY with respect to the game and the console.

USAGE
-----
  # On the PC that owns the game, while you host a LAN session:
  python dl_first_experiment.py --test a --seconds 180

  # On a machine on the Xbox's LAN (or the same LAN as both):
  python dl_first_experiment.py --test b --seconds 120

  # All-in-one on one machine that has both games' network on the same LAN:
  python dl_first_experiment.py --test all --seconds 180

  # Include DNS observation (needs the DNS logger running separately):
  python dl_first_experiment.py --test c --dns-port 53
"""
import argparse
import binascii
import datetime
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dl_lan_probe as LP  # noqa: E402

DL_DISCOVERY_PORT = 26101
DL_GAME_PORT = 26100


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def test_a(seconds, port, verbose):
    """
    TEST A - can we observe the PC game's own LAN beacons?
    Success => the LAN path is live in this build and our decode is correct.
    Failure => port assumption wrong, or LAN mode differs in this build.
    """
    print("=" * 76)
    print("TEST A - PC LAN beacon observation")
    print("=" * 76)
    print("Listening on udp/%d and broadcasting a probe every 5 s." % port)
    print("NOW DO THIS:")
    print("  1. Launch Dying Light on this PC")
    print("  2. MAIN MENU -> OPTIONS -> ONLINE -> GAME TYPE -> LAN")
    print("  3. Host a co-op session (or open FIND GAMES so it scans)")
    print("  4. Leave it running; this test will report what it sees.")
    print()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    try:
        s.bind(("0.0.0.0", port))
    except OSError as e:
        print("[-] bind udp/%d failed: %s" % (port, e))
        print("    (If the GAME is currently running in LAN mode it may already hold")
        print("     this port. Retry after closing the game, or run with --port 26102")
        print("     and rely on the broadcast side only.)")
        return None

    probe = LP.build_packet(0, encoding="literal")
    seen = {}
    end = time.time() + seconds
    next_bcast = 0.0
    print("[%s] started" % ts())
    while time.time() < end:
        now = time.time()
        if now >= next_bcast:
            for tgt in ("255.255.255.255", "127.0.0.1"):
                try:
                    s.sendto(probe, (tgt, port))
                except OSError:
                    pass
            next_bcast = now + 5
        s.settimeout(0.5)
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break
        key = addr[0]
        if key not in seen:
            seen[key] = 0
        seen[key] += 1
        fields, notes = LP.parse_packet(data)
        print("\n[%s] from %s:%d len=%d" % (ts(), addr[0], addr[1], len(data)))
        for n in notes:
            print("    " + n)
        if verbose:
            print(LP.hexdump(data))
    s.close()

    # Our own broadcast comes back addressed from one of THIS machine's own
    # interface addresses. Exclude every local IP, else we "detect" ourselves.
    local_ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            local_ips.add(info[4][0])
    except Exception:
        pass
    try:
        probe_ip = socket.gethostbyname(socket.gethostname())
        local_ips.add(probe_ip)
    except Exception:
        pass
    # also the address the socket would use to reach the outside world
    try:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s2.connect(("8.8.8.8", 53))
        local_ips.add(s2.getsockname()[0])
        s2.close()
    except Exception:
        pass
    local_ips.add("127.0.0.1")
    local_ips.add("0.0.0.0")
    local_ips.discard("")

    real = {k: v for k, v in seen.items() if k not in local_ips}
    print("\n[%s] TEST A result: %d source address(es) observed "
          "(%d excluded as local)" % (ts(), len(seen), len(seen) - len(real)))
    for k, v in sorted(seen.items()):
        tag = ("  <-- LOCAL (this PC), excluded" if k in local_ips
               else "  <-- EXTERNAL: likely the game or a real peer")
        print("    %-20s %4d packets%s" % (k, v, tag))
    if real:
        print("\n  VERDICT: LAN beacons from an EXTERNAL host observed on udp/%d." % port)
        print("  => The LAN path is live and our WD6C decode is correct.")
        print("  => Proceed to TEST B on the Xbox's network.")
    else:
        print("\n  VERDICT: no EXTERNAL beacons seen (only this PC's own).")
        print("  Possible causes, in order of likelihood:")
        print("    1. The game was not actually in LAN mode / not hosting.")
        print("    2. This build uses a different discovery port (check with")
        print("       dl_capture.py --stats while the game runs, looking for a")
        print("       non-standard UDP port near 26100).")
        print("    3. LAN discovery is broadcast-only and your host is not on the")
        print("       same subnet segment (a router may block broadcast).")
    return bool(real)


def test_b(seconds, port):
    """
    TEST B - does the Xbox One speak the WD6C LAN protocol at all?
    Run from a machine on the Xbox's LAN, with the Xbox One on and (if it has
    one) set to LAN matchmaking.
    """
    print("=" * 76)
    print("TEST B - Xbox One reachability on the WD6C LAN path")
    print("=" * 76)
    print("Broadcasting probes on udp/%d and listening for replies." % port)
    print("NOW DO THIS (on the Xbox One):")
    print("  1. Turn the console on, launch Dying Light")
    print("  2. If the console has a LAN / Local / 'Same Network' matchmaking")
    print("     option, select it and host or scan.")
    print("  3. Leave it running.")
    print()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    try:
        s.bind(("0.0.0.0", port))
    except OSError as e:
        print("[-] bind udp/%d failed: %s" % (port, e))
        return None

    probes = [LP.build_packet(t, encoding="literal") for t in range(6)]
    probes += [LP.build_packet(t, encoding="hashed") for t in range(6)]
    seen = {}
    end = time.time() + seconds
    next_bcast = 0.0
    while time.time() < end:
        now = time.time()
        if now >= next_bcast:
            for p in probes:
                try:
                    s.sendto(p, ("255.255.255.255", port))
                except OSError:
                    pass
            next_bcast = now + 3
        s.settimeout(0.5)
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break
        if addr[0] in ("127.0.0.1", "0.0.0.0"):
            continue
        seen[addr[0]] = seen.get(addr[0], 0) + 1
        fields, notes = LP.parse_packet(data)
        print("\n[%s] from %s:%d len=%d" % (ts(), addr[0], addr[1], len(data)))
        for n in notes:
            print("    " + n)
        print(LP.hexdump(data))
    s.close()
    print("\n[%s] TEST B result: %d external source(s)" % (ts(), len(seen)))
    for k, v in sorted(seen.items()):
        print("    %-20s %4d packets" % (k, v))
    if seen:
        print("\n  VERDICT: something on this LAN speaks WD6C.")
        print("  => Compare the decoded field values against the PC's to see if")
        print("     the Xbox uses the SAME GameId/PlatformId/Type values.")
        print("     If yes, a LAN bridge (approach D) becomes viable.")
    else:
        print("\n  VERDICT: nothing on this LAN answered.")
        print("  => Either the console has no LAN mode, it uses a different")
        print("     protocol/port, or it needs an Internet-mediated session.")
        print("  => Approaches D and E are dead; only C/F/G remain, all of which")
        print("     require a protocol translation that cannot be validated")
        print("     without observing the console.")
    return bool(seen)


def test_c(dns_port, seconds):
    print("=" * 76)
    print("TEST C - DNS inventory for the game")
    print("=" * 76)
    print("This does NOT run a DNS server; it queries one so you can confirm")
    print("the resolver you will point the game at answers correctly.")
    print("Start dl_dns_logger.py separately, then run:")
    print("  python dl_dns_logger.py --listen 0.0.0.0 --port %d --upstream 1.1.1.1 --log dl_dns.log" % dns_port)
    print("and set this PC's DNS to <that machine>.")
    print()
    for name in ("api.epicgames.dev", "sdkconfig.epicgames.dev",
                 "pls.dyinglightgame.com", "plsdev.dyinglightgame.com"):
        try:
            ans = socket.getaddrinfo(name, None, socket.AF_INET)
            ips = sorted({a[4][0] for a in ans})
            print("  %-30s -> %s" % (name, ", ".join(ips)))
        except Exception as e:
            print("  %-30s -> ERROR %s" % (name, e))


def main():
    ap = argparse.ArgumentParser(description="Dying Light crossplay - first experiment harness")
    ap.add_argument("--test", default="a", choices=["a", "b", "c", "all"])
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--port", type=int, default=DL_DISCOVERY_PORT)
    ap.add_argument("--dns-port", type=int, default=53)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("Dying Light 1 crossplay - first experiment")
    print("started %s" % datetime.datetime.now().isoformat(timespec="seconds"))
    print()

    results = {}
    if args.test in ("a", "all"):
        results["A_pc_lan_beacons"] = test_a(args.seconds, args.port, args.verbose)
    if args.test in ("b", "all"):
        results["B_xbox_lan_reachability"] = test_b(args.seconds, args.port)
    if args.test in ("c", "all"):
        test_c(args.dns_port, args.seconds)

    print()
    print("=" * 76)
    print("SUMMARY")
    print("=" * 76)
    for k, v in results.items():
        state = "PASS" if v else ("FAIL" if v is not None else "ERROR")
        print("  %-32s %s" % (k, state))
    print()
    print("Next: report which of the above you observed, and paste the")
    print("decoded field lines + any hexdump from this tool's output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
