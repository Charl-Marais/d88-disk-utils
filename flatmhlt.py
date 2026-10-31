#!/usr/bin/env python3
"""Flatten a Mahalito disk image.

Mahalito compresses the data file (*.dat) with a simple algorithm. This tool
uncompresses it while keeping the output a valid Mahalito image. The flattened
.dat can then be loop-mounted, e.g.  mount -t msdos -o loop pc100dos.dat /mnt
"""
import os
import sys

from diskutil import (ImageError, find_data_file, parse_mhlt_header, read_exact,
                      split_name)

USAGE = """\
% flatmhlt.py pc100dos.2dd [pc100dos.dat] flat
=> converts pc100dos.2dd and pc100dos.dat to
   a flat Mahalito image flat.2dd and flat.dat
"""


def flatten(meta, data, flat_meta, flat_data) -> None:
    header = read_exact(meta, 11, "Mahalito header")
    _fmt, ncyl = parse_mhlt_header(header)
    flat_meta.write(header)
    for _ in range(ncyl * 2):
        trk_hdr = read_exact(meta, 2, "track header")
        flat_meta.write(trk_hdr)
        for _ in range(trk_hdr[0]):
            repp, repd, c, h, r, slen, rslen, ddam = read_exact(meta, 8, "sector header")
            flat_meta.write(bytes([0, 0, c, h, r, slen, rslen, ddam]))
            sbytes = 128 << slen
            flat_data.write(bytes([repd]) * sbytes if repp
                            else read_exact(data, sbytes, "data file"))


def main(argv) -> int:
    if len(argv) < 2:
        sys.stderr.write(USAGE)
        return 1
    try:
        metapath = argv[0]
        datapath = argv[1] if len(argv) >= 3 else find_data_file(metapath)
        _, _, suffix = split_name(metapath)
        out_meta, out_data = argv[-1] + suffix, argv[-1] + ".dat"
        for src in (metapath, datapath):         # never truncate an input file
            for dst in (out_meta, out_data):
                if os.path.exists(dst) and os.path.samefile(src, dst):
                    raise ImageError(f"output {dst} would overwrite input {src}")
        with open(metapath, "rb") as m, open(datapath, "rb") as d, \
                open(out_meta, "wb") as fm, open(out_data, "wb") as fd:
            flatten(m, d, fm, fd)
    except (ImageError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
