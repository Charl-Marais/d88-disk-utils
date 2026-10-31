#!/usr/bin/env python3
"""Converts a D88 image (concatenated images supported) to Mahalito image(s)."""
import struct
import sys

from diskutil import (D88_SECTOR, ImageError, iter_d88_headers, mhlt_header,
                      read_exact, warn, write_sector)

USAGE = """\
% d882mhlt.py input.d88 output
=> converts input.d88 to a Mahalito image output.{2d,2dd,2hd} and output.dat
"""


def convert(path: str, outbase: str) -> None:
    with open(path, "rb") as fh:
        total = fh.seek(0, 2)
        for n, img in enumerate(iter_d88_headers(fh), 1):
            if img.type_name == "?":
                raise ImageError(f"unknown D88 disk type 0x{img.type_code:02x}")
            # More than one image in the file -> output#1, output#2, ...
            base = f"{outbase}#{n}" if total > img.length else outbase
            metaname = f"{base}.{img.type_name}"
            dataname = f"{base}.dat"
            warn(f"{img.title} => {metaname} and {dataname}")
            convert_one(fh, img, metaname, dataname)


def read_track_offsets(fh, top: int):
    fh.seek(top + 32)
    first = struct.unpack("<I", read_exact(fh, 4, "track table"))[0]
    nbytes = first - 0x20
    if nbytes < 4 or nbytes % 4:
        raise ImageError(f"bad first track offset 0x{first:x}")
    rest = read_exact(fh, nbytes - 4, "track table")
    return [first] + list(struct.unpack(f"<{nbytes // 4 - 1}I", rest))


def convert_one(fh, img, metaname: str, dataname: str) -> None:
    top = img.offset
    offs = read_track_offsets(fh, top)
    maxtrk = max((i for i, o in enumerate(offs) if o > 0), default=-1)
    if maxtrk < 0:
        raise ImageError("image contains no tracks")

    with open(metaname, "wb") as meta, open(dataname, "wb") as data:
        meta.write(mhlt_header(img.type_name, (maxtrk + 1) // 2))
        for trk in range(maxtrk + 1):
            if not offs[trk]:                 # hole: probably an unformatted track
                meta.write(struct.pack("<BB", 0, 1))
                warn(f"WARN: empty track at track {trk}")
                continue
            fh.seek(top + offs[trk])
            sec = 0
            while True:
                c, h, r, n, nsec, den, dele, _stat, dsz = D88_SECTOR.unpack(
                    read_exact(fh, 16, "sector header"))
                if sec == 0:
                    meta.write(struct.pack("<BB", nsec, 0 if den == 0x40 else 1))
                if nsec == 0:
                    break
                payload = read_exact(fh, dsz, "sector data")
                sec += 1
                write_sector(meta, data, payload, c, h, r, n, 1 if dele == 0x10 else 0)
                if sec >= nsec:
                    break


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
