#!/usr/bin/env python3
"""Converts an Anex86 FDI disk image to a Mahalito disk image.

Reverse-engineered FDI header (non-authoritative), little-endian uint32 fields:
    0x00 zero
    0x04 density          (0x30 = 1.44MB, 0x90 = 1.2MB, 0x10 = 2DD?)
    0x08 header_size      (0x1000)
    0x0c image_body_size  (0x134000 = 1261568)
    0x10 sector_size      (0x0400)
    0x14 sectors_per_trk  (8)
    0x18 heads            (2)
    0x1c cylinders        (0x4d = 77)
"""
import struct
import sys

from diskutil import ImageError, mhlt_header, read_exact, warn, write_sector

USAGE = """\
% fdi2mhlt.py input.fdi output
=> converts input.fdi to a Mahalito image output.2hd and output.dat
"""


def calc_n(sec_sz: int) -> int:
    """Sector size code N such that sec_sz == 128 << N."""
    return (sec_sz // 128).bit_length() - 1


def density_interp(den_val: int) -> str:
    if den_val & 0x20:
        warn("WARNING : 1.44 MB image detected.\n"
             "WARNING(cont): This image probably cannot be used with Mahalito.\n"
             "WARNING(cont): Use flatmhlt.py to flatten the output,\n"
             "WARNING(cont): then dd the dat file to 1.44 MB formatted diskette.")
        return "2hd"
    if (den_val & 0xE0) == 0:
        return "2dd"
    return "2hd"


def convert(fdipath: str, outbase: str) -> None:
    with open(fdipath, "rb") as fdi:
        fdisz = fdi.seek(0, 2)
        fdi.seek(4)
        (den, hdr_sz, body_sz, sec_sz, sec_per_trk, nhead, ncyl) = struct.unpack(
            "<7I", read_exact(fdi, 0x1C, "FDI header"))
        warn(f"FDI: {fdisz} bytes ({hdr_sz} header + {body_sz} body)")
        if fdisz != hdr_sz + body_sz:
            warn("WARNING: FDI file size does not match header!")
        calc_body = ncyl * nhead * sec_per_trk * sec_sz
        warn(f"{ncyl} cyls, {nhead} heads, {sec_per_trk} sectors/track, "
             f"{sec_sz} bytes/sector => body {calc_body} bytes")
        if calc_body != body_sz:
            warn("WARNING: Body size does not match geometry!")
        if sec_sz < 128 or sec_sz & (sec_sz - 1) or not sec_per_trk or not nhead:
            raise ImageError("unsupported or corrupt FDI geometry")

        fdi.seek(hdr_sz)
        n = calc_n(sec_sz)
        fmt = density_interp(den)
        metaname, dataname = f"{outbase}.{fmt}", f"{outbase}.dat"
        warn(f"writing to {metaname} and {dataname}")

        with open(metaname, "wb") as meta, open(dataname, "wb") as data:
            meta.write(mhlt_header(fmt, ncyl))
            for trk in range(ncyl * nhead):
                meta.write(struct.pack("<BB", sec_per_trk, 1))      # MFM
                for sec in range(sec_per_trk):
                    payload = fdi.read(sec_sz)
                    if len(payload) < sec_sz:
                        continue                                    # ignore short sector
                    # Cylinder/head derived as trk//2 and trk&1, as in the original.
                    write_sector(meta, data, payload, trk // 2, trk & 1, sec + 1, n, 0)


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
