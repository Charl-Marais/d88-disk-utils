#!/usr/bin/env python3
"""Mahalito to D88 disk image converter (writes the D88 image to stdout)."""
import struct
import sys

from diskutil import (D88_HEADER, D88_SECTOR, ImageError, find_data_file,
                      parse_mhlt_header, read_exact, split_name)

USAGE = """\
Example:
  mhlt2d88.py pc100dos.2dd [pc100dos.dat] > pc100dos.d88
  # pc100dos.2dd, pc100dos.dat => pc100dos.d88
"""

D88_TABLE_END = 0x2B0                      # 0x20 header + 164 * 4-byte track pointers
D88_TYPE = {"2hd": 0x20, "2dd": 0x10, "2d": 0x00}


def mahalito_to_d88(meta, data, title: str) -> bytes:
    fmt, ncyl = parse_mhlt_header(read_exact(meta, 11, "Mahalito header"))
    if ncyl > 82:
        raise ImageError(f"{ncyl} cylinders do not fit in a D88 track table")

    offsets = []
    tracks = bytearray()
    for _ in range(ncyl):
        for _ in range(2):                              # two heads per cylinder
            nsec, mfm = read_exact(meta, 2, "track header")
            offsets.append(D88_TABLE_END + len(tracks))
            if nsec == 0:
                # Unformatted track. Kept exactly as in the Perl original:
                # an all-zero sector header followed by 256 zero bytes.
                tracks += D88_SECTOR.pack(0, 0, 0, 0, 0, 0, 0, 0, 0) + bytes(256)
                continue
            for _ in range(nsec):
                repp, repd, c, h, r, slen, _rslen, ddam = read_exact(meta, 8, "sector header")
                if slen > 8:
                    raise ImageError(f"unreasonable sector size code N={slen}")
                sbytes = 128 << slen
                payload = bytes([repd]) * sbytes if repp else read_exact(data, sbytes, "data file")
                tracks += D88_SECTOR.pack(
                    c, h, r, slen, nsec,
                    0x00 if mfm else 0x40,             # density: 0x40 = FM
                    0x10 if ddam else 0x00,            # deleted-data mark
                    0x00,                              # status
                    sbytes) + payload

    offsets += [0] * (164 - len(offsets))
    size = D88_TABLE_END + len(tracks)
    # 16 chars max so the title stays NUL-terminated
    title_b = title.encode("shift_jis", errors="replace")[:16]
    return (D88_HEADER.pack(title_b, 0, D88_TYPE[fmt], size)
            + struct.pack("<164I", *offsets) + bytes(tracks))


def main(argv) -> int:
    if not 1 <= len(argv) <= 2:
        sys.stderr.write(USAGE)
        return 1
    try:
        _, stem, _ = split_name(argv[0])
        datapath = argv[1] if len(argv) == 2 else find_data_file(argv[0])
        if sys.stdout.isatty():
            raise ImageError("refusing to write binary data to a terminal; redirect stdout")
        with open(argv[0], "rb") as meta, open(datapath, "rb") as data:
            out = mahalito_to_d88(meta, data, stem)
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
    except (ImageError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
