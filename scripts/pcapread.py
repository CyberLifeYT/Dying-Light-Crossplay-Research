"""
pcapng reader (minimal) + classic pcap reader, returning a list of raw
Ethernet/IP frames so dl_session_probe.py can triage either format.

pktmon's `etl2pcap` writes pcapng, NOT classic pcap, so the triage tool
must understand both.
"""
import struct

PCAPNG_SHB = 0x0A0D0D0A
PCAPNG_IDB = 0x00000001
PCAPNG_EPB = 0x00000006
PCAPNG_SPB = 0x00000003
PCAPNG_PB = 0x00000002  # obsolete packet block

LINKTYPE_NULL = 0
LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101
LINKTYPE_LINUX_SLL = 113
LINKTYPE_IPV4 = 228
LINKTYPE_IPV6 = 229


def read_pcapng(data):
    """
    Yield (linktype, raw_packet_bytes) from a pcapng file.

    pcapng block layout (RFC 1.10):
        Block Type    (4)
        Block Total Length (4)
        Body
        Block Total Length (4)   <- repeated
    The Section Header Block is special: its Block Type is 0x0A0D0D0A and
    the byte-order magic lives in the body.
    """
    off = 0
    endian = "<"
    linktypes = []
    while off + 12 <= len(data):
        btype = struct.unpack_from(endian + "I", data, off)[0]
        if btype == PCAPNG_SHB:
            # byte-order magic is the first 4 bytes of the body
            bom = data[off + 8:off + 12]
            if bom == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif bom == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                break
            btype = struct.unpack_from(endian + "I", data, off)[0]
        blen = struct.unpack_from(endian + "I", data, off + 4)[0]
        if blen < 12 or off + blen > len(data):
            break
        body = data[off + 8: off + blen - 4]
        if btype == PCAPNG_IDB:
            lt = struct.unpack_from(endian + "H", body, 0)[0]
            linktypes.append(lt)
        elif btype == PCAPNG_EPB:
            iface, ts_hi, ts_lo, caplen, origlen = struct.unpack_from(
                endian + "IIIII", body, 0)
            pkt = body[20:20 + caplen]
            lt = linktypes[iface] if iface < len(linktypes) else LINKTYPE_ETHERNET
            yield lt, pkt
        elif btype == PCAPNG_SPB:
            origlen = struct.unpack_from(endian + "I", body, 0)[0]
            pkt = body[4:4 + origlen]
            lt = linktypes[0] if linktypes else LINKTYPE_ETHERNET
            yield lt, pkt
        elif btype == PCAPNG_PB:
            iface = struct.unpack_from(endian + "H", body, 0)[0]
            caplen = struct.unpack_from(endian + "I", body, 12)[0]
            pkt = body[16:16 + caplen]
            lt = linktypes[iface] if iface < len(linktypes) else LINKTYPE_ETHERNET
            yield lt, pkt
        off += blen


def read_classic_pcap(data):
    """Yield (linktype, raw_packet_bytes) from a classic pcap file."""
    if len(data) < 24:
        return
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian, nano = "<", False
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian, nano = ">", False
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian, nano = "<", True
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian, nano = ">", True
    else:
        return
    linktype = struct.unpack(endian + "I", data[20:24])[0]
    off = 24
    while off + 16 <= len(data):
        ts, tus, incl, orig = struct.unpack(endian + "IIII", data[off:off + 16])
        off += 16
        pkt = data[off:off + incl]
        off += incl
        yield linktype, pkt


def read_any(path):
    """Return (format_name, list_of_(linktype, pkt))."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 4:
        return "empty", []
    if data[:4] == b"\x0a\x0d\x0d\x0a":
        return "pcapng", list(read_pcapng(data))
    if data[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4",
                    b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        return "pcap", list(read_classic_pcap(data))
    return "unknown", []
