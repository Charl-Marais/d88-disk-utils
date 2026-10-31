# d88split (Python port)

Old-computer disk image utilities for **D88/D77, Mahalito, XDF, FDI and NFD** images.

This is a Python 3 port of [**tomari/d88split**](https://github.com/tomari/d88split) by H. Tomari,
which was written in Perl. The original GitHub repository is archived and read-only; the project
was migrated to GitLab: <https://gitlab.com/tomari/d88split>.

The original code is released to the public domain, and this port keeps the same spirit.
All credit for the file-format work and the original tool design belongs to the original author.

Requires Python 3.8 or newer. There are no third-party dependencies.

## Tools

| Script | Purpose |
|---|---|
| `d88split.py` | Lists or splits concatenated D88/D77 disk images |
| `d882mhlt.py` | D88/D77 to Mahalito |
| `mhlt2d88.py` | Mahalito to D88 |
| `flatmhlt.py` | Uncompress ("flatten") a Mahalito image |
| `xdf2mhlt.py` | X68000 XDF to Mahalito |
| `fdi2mhlt.py` | Anex86 FDI to Mahalito |
| `nfd2mhlt.py` | T98-Next NFD to Mahalito |

Shared code lives in `diskutil.py`. The scripts keep the names and command-line usage of the Perl
originals, with a `.py` extension instead of `.pl`.

## About the formats

All of these are ways of storing the contents of a floppy disk as a file, mostly so that old
Japanese home computers can be emulated or their disks archived.

- **D88** is an image format for floppy disks from the NEC PC-88 and PC-98 computers.
  It stores each track and sector with its own header, so it can describe unusual or copy-protected
  disks as well as normal ones. Several disks can be joined into one file.
- **D77** is the same format, used for the Fujitsu FM-77 series.
- **Mahalito** is a disk image tool for the PC-98, used to read and write real floppy disks.
  A Mahalito image is a pair of files: a small metadata file (`.2d`, `.2dd` or `.2hd`, named after
  the disk type) describing the tracks and sectors, and a `.dat` file holding the sector data.
  Sectors in which every byte is identical are not stored in the `.dat` file, which is how it
  compresses the image.
- **XDF** is a plain, headerless dump of a Sharp X68000 floppy disk. A standard 2HD disk is
  77 cylinders, 2 heads, 8 sectors of 1024 bytes, or 1,261,568 bytes in total.
- **FDI** is the disk image format of Anex86, a PC-98 emulator. It has a 4096-byte header followed
  by the raw sector data.
- **NFD** is the disk image format of T98-Next, another PC-98 emulator. It records per-sector
  information, so it can represent more than a plain dump. This tool supports revision R0, and R1
  experimentally.

The 2D, 2DD and 2HD names are the standard double-sided floppy disk densities. 2HD is the
high-density type.

## d88split

Splits concatenated D88/D77 disk images.

List the images packed in a file:

```
% python3 d88split.py l kohaku.d77
Image             Protect Type      Bytes
----------------------------------------
Kohaku_1                0 2D       473776
Kohaku_2                0 2D       473776
Kohaku_3                0 2D       473776
Kohaku_4                0 2D       473776
```

Extract the images into the current directory:

```
% python3 d88split.py e kohaku.d77
Kohaku_1 => kohaku#1.d77 ( 473776 bytes)
Kohaku_2 => kohaku#2.d77 ( 473776 bytes)
Kohaku_3 => kohaku#3.d77 ( 473776 bytes)
Kohaku_4 => kohaku#4.d77 ( 473776 bytes)
```

To join D88 files back together, concatenate them: `cat a.d88 b.d88 > c.d88`

## d882mhlt

Converts a D88/D77 disk image to Mahalito format. Concatenated D88 images are supported.

```
% python3 d882mhlt.py kohaku.d77 ko
Kohaku_1 => ko#1.2d and ko#1.dat
Kohaku_2 => ko#2.2d and ko#2.dat
Kohaku_3 => ko#3.2d and ko#3.dat
Kohaku_4 => ko#4.2d and ko#4.dat
```

## mhlt2d88

Converts a Mahalito disk image to D88 format. The D88 image is written to standard output.

```
python3 mhlt2d88.py pc100dos.2dd > pc100dos.d88
```

`pc100dos.2dd` and `pc100dos.dat` are converted to `pc100dos.d88`. A different data file can be
given as a second argument.

## flatmhlt

Flattens a Mahalito disk image so its contents can be read or modified.

Mahalito compresses the data file (`*.dat`) with a simple algorithm. This utility uncompresses it
while keeping the output a valid Mahalito disk image. The flattened data file can then be mounted
on Linux, for example:

```
% mount -t msdos -o loop pc100dos.dat /mnt
```

After making changes, the flattened image can be written back to a floppy disk using Mahalito.

```
% python3 flatmhlt.py pc100dos.2dd [pc100dos.dat] flat
    => converts pc100dos.2dd and pc100dos.dat to
       a flat Mahalito image flat.2dd and flat.dat
```

## xdf2mhlt

Converts an X68000 XDF disk image to Mahalito format.

```
python3 xdf2mhlt.py sharrier.xdf sharrier
```

Converts `sharrier.xdf` to `sharrier.2hd` and `sharrier.dat`.

## fdi2mhlt

Converts an Anex86 FDI disk image to Mahalito format.

2HD and 2DD images are supported (based on reverse-engineering of the format). 1.44 MB images are
also converted, but Mahalito itself does not support them. Use `flatmhlt.py`, then `dd` the `.dat`
file to a standard-formatted 1.44 MB diskette.

```
$ python3 fdi2mhlt.py blkwarsv.fdi blkwarsv
FDI: 1265664 bytes (4096 header + 1261568 body)
77 cyls, 2 heads, 8 sectors/track, 1024 bytes/sector => body 1261568 bytes
writing to blkwarsv.2hd and blkwarsv.dat
```

## nfd2mhlt

Converts a T98-Next NFD floppy disk image to Mahalito format.

Tested with NFD R0 images only. NFD R1 support is experimental and untested, because no R1 image
was available to the original author.

```
% python3 nfd2mhlt.py No1.NFD dos62no1
NFD R0 #cyl 77 #hd 2 #sec 8 (1024 byte/sector)
writing to dos62no1.2hd and dos62no1.dat
```

## Differences from the Perl original

- `mhlt2d88.py` writes the deleted-data (DDAM) flag into the D88 "deleted" byte, where the Perl
  version wrote it into the wrong field. This makes D88 to Mahalito to D88 round trips lossless.
- Mahalito version strings are matched ignoring trailing spaces and NUL bytes.
- `flatmhlt.py` refuses to overwrite one of its own input files.
- Truncated or corrupt images produce an error message and a non-zero exit code.

## Tests

```
python3 -m unittest discover -s tests -v
```

The tests use synthetic images, so they do not need any real disk images. They have not been
compared against the Perl scripts or run against a large collection of real disks.

## References

These are the references listed by the original project:

1. `mahalito.doc` in `mhlt214.lzh`: describes the Mahalito format.
2. `quasi88-0.6.4/document/FORMAT.TXT` in `quasi88-0.6.4.tgz`: describes the D88 format.
3. <http://www.geocities.jp/t98next/nfdr0.txt>: NFD R0 format specification.
4. <http://www.geocities.jp/t98next/nfdr1.txt>: NFD R1 format specification.

The two NFD links point to a site that has since closed, so they may no longer work.

Original project: <https://github.com/tomari/d88split> (archived) and
<https://gitlab.com/tomari/d88split>.
