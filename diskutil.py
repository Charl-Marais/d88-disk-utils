"""Shared helpers for the d88split utilities (Python port of the Perl originals).

Original Perl code: 2013-2014 H.Tomari, public domain.
"""
import os
import struct
import sys
from typing import Iterator, NamedTuple


class ImageError(Exception):
    """Raised for malformed, truncated or unsupported disk images."""


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------
def read_exact(fh, n: int, what: str = "data") -> bytes:
    buf = fh.read(n)
    if len(buf) != n:
        raise ImageError(f"unexpected end of file while reading {what}")
    return buf


def split_name(path: str):
    """Rough equivalent of Perl's fileparse($path, qr/\\.[^.]*/): (dir, stem, suffix)."""
    d, base = os.path.split(path)
    stem, suffix = os.path.splitext(base)
    return d, stem, suffix


def detect_repeat(data: bytes):
    """Return the byte value if every byte in `data` is identical, else None."""
    if data and data.count(data[:1]) == len(data):
        return data[0]
    return None


# --------------------------------------------------------------------------
# Mahalito
# --------------------------------------------------------------------------
# 10-byte identification string at the start of the metadata file (*.2hd etc.)
MHLT_ID = {"2hd": b"ver 1.10 ", "2dd": b"2DD ver1.0", "2d": b"2D ver1.0"}
_ID_TO_FMT = {v.rstrip(b" \0"): k for k, v in MHLT_ID.items()}


def mhlt_header(fmt: str, ncyl: int) -> bytes:
    if not 0 <= ncyl <= 255:
        raise ImageError(f"cylinder count {ncyl} does not fit in a Mahalito header")
    return MHLT_ID[fmt].ljust(10, b"\0") + bytes([ncyl])


def parse_mhlt_header(buf: bytes):
    """Return (format, ncyl) from the 11-byte Mahalito header."""
    if len(buf) < 11:
        raise ImageError("Not a Mahalito disk image (header too short)")
    # Trailing spaces/NULs are ignored so both padding styles are accepted.
    fmt = _ID_TO_FMT.get(buf[:10].rstrip(b" \0"))
    if fmt is None:
        raise ImageError("Unknown version string: not a Mahalito image?")
    return fmt, buf[10]


def write_sector(meta, data, payload: bytes, c: int, h: int, r: int, n: int, ddam: int) -> None:
    """Write one sector: 8-byte header to `meta`, payload to `data` unless it is a repeat."""
    rep = detect_repeat(payload)
    meta.write(struct.pack("<8B", 1 if rep is not None else 0, rep or 0,
                           c, h, r, n, n, ddam))
    if rep is None:
        data.write(payload)


def find_data_file(meta_path: str) -> str:
    d, stem, _ = split_name(meta_path)
    tried = [os.path.join(d, stem + ext) for ext in (".dat", ".DAT")]
    for p in tried:
        if os.path.exists(p):
            return p
    raise ImageError(f"data file not found (tried {tried[0]} and {tried[1]})")


# --------------------------------------------------------------------------
# D88
# --------------------------------------------------------------------------
D88_HEADER = struct.Struct("<17s9xBBI")          # title, write-protect, type, size  (32 bytes)
D88_SECTOR = struct.Struct("<BBBBHBBB5xH")       # C H R N nsec density deleted status size (16 bytes)
D88_TYPES = {0: "2d", 1: "2dd", 2: "2hd"}        # indexed by (type byte >> 4)


class D88Image(NamedTuple):
    offset: int
    title: str
    protect: int
    type_code: int
    length: int

    @property
    def type_name(self) -> str:
        return D88_TYPES.get(self.type_code >> 4, "?")


def decode_title(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("shift_jis", errors="replace")


def iter_d88_headers(fh) -> Iterator[D88Image]:
    """Yield a D88Image for each image in a (possibly concatenated) D88/D77 file.

    The file position is reset by the generator before each header, so callers
    may seek/read freely between iterations.
    """
    size = fh.seek(0, 2)
    pos = 0
    while pos < size:
        fh.seek(pos)
        title, wp, typ, length = D88_HEADER.unpack(read_exact(fh, 32, "D88 header"))
        if length < 32:
            raise ImageError(f"bad image length {length} at offset {pos}")
        if pos + length > size:
            warn(f"WARN: image at offset {pos} is truncated "
                 f"({size - pos} of {length} bytes present)")
        yield D88Image(pos, decode_title(title), wp, typ, length)
        pos += length
