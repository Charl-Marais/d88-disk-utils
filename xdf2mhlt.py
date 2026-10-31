#!/usr/bin/env python3
"""Converts an X68k XDF disk image to a Mahalito disk image (output.2hd + output.dat)."""
import struct
import sys

from diskutil import ImageError, mhlt_header, warn, write_sector

USAGE = """\
% xdf2mhlt.py input.xdf output
=> converts input.xdf to a Mahalito image output.2hd and output.dat
"""

TRACK_BYTES = 8192        # 8 sectors x 1024 bytes
SECTOR_BYTES = 1024


def convert(xdfpath: str, outbase: str) -> None:
    metaname, dataname = outbase + ".2hd", outbase + ".dat"
    warn(f"writing to {metaname} and {dataname}")
    with open(xdfpath, "rb") as xdf:
        size = xdf.seek(0, 2)
        xdf.seek(0)
        ntrk = (size + TRACK_BYTES - 1) // TRACK_BYTES
        ncyl = (ntrk + 1) // 2
        warn(f"XDF is {size} bytes long. #track= {ntrk}, #cyl= {ncyl}")
        with open(metaname, "wb") as meta, open(dataname, "wb") as data:
            meta.write(mhlt_header("2hd", ncyl))
            for trk in range(ntrk):
                # The Perl original always declared 8 sectors per track, even
                # for a truncated final track; short sectors are skipped.
                nsector = TRACK_BYTES // SECTOR_BYTES
                meta.write(struct.pack("<BB", nsector, 1))          # MFM
                for sec in range(nsector):
                    payload = xdf.read(SECTOR_BYTES)
                    if len(payload) < SECTOR_BYTES:
                        continue                                    # ignore short sector
                    write_sector(meta, data, payload,
                                 trk // 2, trk & 1, sec + 1, 3, 0)


def main(argv) -> int:
    if len(argv) != 2:
        sys.stderr.write(USAGE)
        return 1
    try:
        convert(argv[0], argv[1])
    except (ImageError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
