#!/usr/bin/env python3
"""D88/D77 multi-volume format splitter.

D88: PC-88/PC-98 floppy disk image
D77: FM77 floppy disk image
"""
import sys

from diskutil import ImageError, iter_d88_headers, split_name

USAGE = """\
d88split l image.d88   # lists images in the file
d88split e image.d88   # extracts images from the file
                       #   image#1.d88, image#2.d88, ...
(To concatenate D88 files use cat a.d88 b.d88 > c.d88 )
"""


def list_images(fh) -> None:
    print(f"{'Image':<17} {'Protect':>7} {'Type':<5} {'Bytes':>9}", file=sys.stderr)
    print("-" * 40, file=sys.stderr)
    for img in iter_d88_headers(fh):
        print(f"{img.title:<17} {1 if img.protect else 0:>7} "
              f"{img.type_name.upper():<5} {img.length:>9}")


def extract_images(fh, srcpath: str) -> None:
    _, stem, suffix = split_name(srcpath)
    for n, img in enumerate(iter_d88_headers(fh), 1):
        dst = f"{stem}#{n}{suffix}"          # written to the current directory
        fh.seek(img.offset)
        data = fh.read(img.length)
        with open(dst, "wb") as out:
            out.write(data)
        print(f"{img.title} => {dst} ( {len(data)} bytes)")


def main(argv) -> int:
    if len(argv) != 2 or argv[0] not in ("l", "e"):
        sys.stderr.write(USAGE)
        return 1
    try:
        with open(argv[1], "rb") as fh:
            if argv[0] == "l":
                list_images(fh)
            else:
                extract_images(fh, argv[1])
    except (ImageError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
