# Dying Light 1 — LAN discovery/game protocol format

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

## The packet structure (LAN discovery)

FUN_1806a78a0 is the dispatcher. It reads a leading byte, then a
*type-tagged* field stream.

The dispatcher accepts a first byte whose low 7 bits select the message
type (0..5) and whose high bit (0x80) marks an "extended" variant.

### Confirmed field-name comparisons

   1. "GameId"        (6-byte literal form, or 4-byte hash form)
      -> then a 4-byte dword compared to **param_2**
   2. "PlatformId"    (10-byte literal form, or 4-byte hash form)
      -> then a 4-byte dword compared to **param_3**

At the call site in FUN_1806a78a0:
    FUN_1806a4ef0(local_88, 0x43364457, 1);

0x43364457 == 0x0000_4336_4457 -> bytes "WD6C" when written big-endian as
ASCII. => **This is a numeric field VALUE that happens to spell "WD6C" in ASCII.**

## Message type dispatch
  0 -> FUN_1806a6340
  1 -> FUN_1806a7060
  2 -> FUN_1806a7f70  (with a flag = (type==3))
  3 -> FUN_1806a7f70
  4 -> FUN_1806a9030  (only if *(int*)(param_1+0x10) == 1)  (flag = type==5)
  5 -> FUN_1806a9030

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

## IMPORTANT CAVEAT
These conclusions are from static analysis of the PC 2022 build only. The
Xbox One 2016 build may use:
  - a different constant instead of 0x43364457,
  - a different field set,
  - a different message-type range.

=> The only credible route to PC<->Xbox is **D/E (LAN discovery bridge) and/or
F (gameplay protocol translation) on top of the LAN path**, not A/B/C.