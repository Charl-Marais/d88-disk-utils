#!/usr/bin/env python3
"""Converts a T98-Next NFD (R0, experimental R1) disk image to a Mahalito image."""
import struct
import sys
from typing import NamedTuple, Optional

from diskutil import ImageError, mhlt_header, read_exact, warn, write_sector

USAGE = """\
% nfd2mhlt.py input.nfd output
=> converts input.nfd to a Mahalito image output.{2hd,2dd} and output.dat
"""

NFD_HEADER = struct.Struct("<15sx256sIBB")    # magic, comment, header size, write-protect, heads
MAGIC_R0 = b"T98FDDIMAGE.R0\0"
MAGIC_R1 = b"T98FDDIMAGE.R1\0"


class Sector(NamedTuple):
    c: int
    h: int
    r: int
    n: int
    mfm: int
    ddam: int
    pda: int
    retry: Optional[int] = None     # R1 only: extra copies stored after the sector


def read_trkinfo_r0(fh):
    secinfo, seccount = [], []
    for _trk in range(163):
        nsec = 0
        for _sec in range(26):
            buf = fh.read(0x10)
            if len(buf) < 0x10 or buf[0] == 0xFF:       # short read / unused slot
                continue
            nsec += 1
            secinfo.append(Sector(buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[10]))
        if nsec > 0:
            seccount.append(nsec)
    return secinfo, seccount, []


def read_trkinfo_r1(fh):
    """Not tested upstream either -- no R1 images were available to the original author."""
    secinfo, seccount, skipafter = [], [], []
    trkptr = struct.unpack("<164I", read_exact(fh, 164 * 4, "R1 track table"))
    for ptr in trkptr:
        if ptr == 0:
            continue
        fh.seek(ptr)
        wsector, wdiag = struct.unpack("<HH", read_exact(fh, 0x10, "R1 track id")[:4])
        seccount.append(wsector)
        for _ in range(wsector):
            b = read_exact(fh, 0x10, "R1 sector id")
            secinfo.append(Sector(b[0], b[1], b[2], b[3], b[4], b[5], b[11], b[10]))
        skip = 0
        for _ in range(wdiag):
            b = read_exact(fh, 0x10, "R1 diagnostic id")
            retry, length = b[9], struct.unpack_from("<I", b, 10)[0]
            skip += (1 + retry) * length
        skipafter.append(skip)
    return secinfo, seccount, skipafter


def detect_media(pda: int, n: int) -> str:
    if pda == 0x30:
        warn("WARNING : 1.44 MB image detected.\n"
             "WARNING(cont): This image probably cannot be used with Mahalito.\n"
             "WARNING(cont): Use flatmhlt.py to flatten the output,\n"
             "WARNING(cont): then dd the dat file to 1.44 MB formatted diskette.")
        return "2hd"
    if pda == 0x10:
        return "2dd"
    if pda == 0x90:
        return "2hd"
    return "2dd" if n == 2 else "2hd"       # dubious fallback, as in the original


def convert(nfdpath: str, outbase: str) -> None:
    with open(nfdpath, "rb") as fh:
        head = read_exact(fh, 0x120, "NFD header")
        magic, _comment, hdr_sz, _prot, nhead = NFD_HEADER.unpack_from(head)
        if magic == MAGIC_R0:
            label = "NFD R0"
            secinfo, seccount, skipafter = read_trkinfo_r0(fh)
        elif magic == MAGIC_R1:
            warn("WARNING: NFD R1 detected. R1 support is experimental.")
            label = "NFD R1"
            secinfo, seccount, skipafter = read_trkinfo_r1(fh)
        else:
            raise ImageError("Invalid magic")
        if not secinfo or not nhead:
            raise ImageError("no sectors found in NFD image")

        mediatype = detect_media(secinfo[0].pda, secinfo[0].n)
        ncyl = len(seccount) // nhead
        warn(f"{label} #cyl {ncyl} #hd {nhead} #sec {seccount[0]} "
             f"({128 << secinfo[0].n} byte/sector)")
        fh.seek(hdr_sz)                                  # move to body

        metaname, dataname = f"{outbase}.{mediatype}", f"{outbase}.dat"
        warn(f"writing to {metaname} and {dataname}")
        with open(metaname, "wb") as meta, open(dataname, "wb") as data:
            meta.write(mhlt_header(mediatype, ncyl))
            secptr = 0
            for s, nsector in enumerate(seccount):
                mfm = secinfo[secptr].mfm if nsector else 1
                meta.write(struct.pack("<BB", nsector, mfm))
                for _ in range(nsector):
                    sec = secinfo[secptr]
                    secptr += 1
                    nbytes = 128 << sec.n
                    payload = fh.read(nbytes)
                    if len(payload) < nbytes:
                        warn("Failed to read input. Trying to continue...")
                        continue
                    write_sector(meta, data, payload, sec.c, sec.h, sec.r, sec.n, sec.ddam)
                    if sec.retry is not None:
                        fh.seek(sec.retry * nbytes, 1)
                if s < len(skipafter) and skipafter[s] > 0:
                    fh.seek(skipafter[s], 1)


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
