# Dying Light 1 — LAN discovery/game protocol format (DECODED from Ghidra)

## The hash function
FUN_1806a4ef0 / FUN_1806a5290 use:
    h = 0
    for c in fieldname_ascii:
        h = (h * 0x29 + c) & 0xFFFFFFFF      # 0x29 == 41
Verified field names and their hashes:

| name        | hash        | LE bytes          |
|-------------|-------------|-------------------|
| "Type"      | 0x005b8392  | 92 83 5B 00       |
| "GameId"    | 0xfb17484f  | 4F 48 17 FB       |
| "PlatformId"| 0x74616c50  | 50 6C 61 74 ("Plat") |
| "ScanId"    | 0x4e3f086a  | 6A 08 3F 4E       |

## The packet structure (LAN discovery, CLobbyScannerLan)

FUN_1806a78a0 is the dispatcher. It reads a leading byte, then a
*type-tagged* field stream. There are two encodings of a field name:

  encoding 1 ("hashed"):  4 bytes = hash(name)
  encoding 2 ("literal"): 1 byte length, then `len` bytes of the ASCII name
                           (compared as a 64-bit little-endian value, e.g.
                            "GameId"  -> 0x0000_6449_616d_6547
                            "Type"    -> 0x0000_6570_7954
                            "PlatformId" -> 0x0000_6449_6c61_7461)

The dispatcher accepts a first byte whose low 7 bits select the message
type (0..5) and whose high bit (0x80) marks an "extended" variant.

### Confirmed field-name comparisons inside FUN_1806a4ef0
The function is a *sequentially matched field reader*: it walks the buffer and
matches a chain of expected fields. Decompiled matches, in order:

  1. "GameId"        (6-byte literal form, or 4-byte hash form)
     -> then a 4-byte dword compared to **param_2**
  2. "PlatformId"    (10-byte literal form, or 4-byte hash form)
     -> then a 4-byte dword compared to **param_3**
  3. a 4-byte dword compared to the constant **1**

At the call site in FUN_1806a78a0:
    FUN_1806a4ef0(local_88, 0x43364457, 1);
i.e. after "GameId" there is a dword expected to equal 0x43364457, then after
"PlatformId" a dword expected to equal 1, then a dword expected to equal 1.

0x43364457 == 0x0000_4336_4457 -> bytes "WD6C" when written big-endian as
ASCII, but the engine compares it as a *numeric dword* after "GameId".
=> **This is a numeric field VALUE that happens to spell "WD6C" in ASCII.**
It is very likely a "game type / application id" constant (0x43364457 =
"WD6C" = "World/Dead City ... Chrome"). This is a *value*, not a magic.

Second call site, FUN_1806a5290 ("read next field"):
    FUN_1806a4ef0 -> compares against "Type" literal (0x65707954 == "Type")
    then reads a dword and switches on it:
        case 0..5  -> accepted (message type 0..5)
This is where the 6 message types come from.

## Message type dispatch (FUN_1806a78a0)
  local_58 (the "type" dword) selects:
    0 -> FUN_1806a6340
    1 -> FUN_1806a7060
    2 -> FUN_1806a7f70  (with a flag = (type==3))
    3 -> FUN_1806a7f70
    4 -> FUN_1806a9030  (only if *(int*)(param_1+0x10) == 1)  (flag = type==5)
    5 -> FUN_1806a9030
    default -> log "Received unknown packet type = %d from address %s:%d"

## So the LAN packet looks like:

    +--------+--------------------------------------------------+
    | hdr    |  "GameId"      (literal 6B or hash 4B)           |
    | byte   |  dword  0x43364457   <- game/app id ("WD6C")      |
    |        |  "PlatformId"  (literal 10B or hash 4B)         |
    |        |  dword  1         <- platform id                  |
    |        |  dword  1         <- ?                             |
    |        |  "Type"        (literal 4B or hash 4B)           |
    |        |  dword  0..5    <- message type                  |
    |        |  ... payload ...                                |
    +--------+--------------------------------------------------+

The leading byte: low7 = message type, high bit = "extended".

## Consequence for the prober
A discovery probe is therefore NOT "magic + fields". It is:
  hdr byte (type) + "GameId" literal + 0x43364457 + "PlatformId" literal
  + 1 + 1 + "Type" literal + <type dword> + payload

Where "GameId"/"PlatformId"/"Type" may be sent in EITHER the literal or the
hashed encoding (the reader accepts both).

## IMPORTANT CAVEAT
These conclusions are from static analysis of the PC 2022 build only. The
Xbox One 2016 build may use:
  - a different constant instead of 0x43364457 (i.e. not "WD6C"),
  - a different field set,
  - a different message-type range.
This must be checked empirically against the Xbox console.
