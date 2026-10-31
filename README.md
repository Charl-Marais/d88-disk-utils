# d88split (Python port)

Python 3.8+ port of tomari/d88split (Perl, public domain). No third-party dependencies.

| Script | Purpose |
|---|---|
| `d88split.py l\|e image.d77` | List / extract images from concatenated D88/D77 files |
| `d882mhlt.py in.d88 out` | D88/D77 -> Mahalito (`out.{2d,2dd,2hd}` + `out.dat`) |
| `mhlt2d88.py in.2dd [in.dat] > out.d88` | Mahalito -> D88 (to stdout) |
| `flatmhlt.py in.2dd [in.dat] flat` | Uncompress a Mahalito `.dat` (`flat.2dd`, `flat.dat`) |
| `xdf2mhlt.py in.xdf out` | X68k XDF -> Mahalito |
| `fdi2mhlt.py in.fdi out` | Anex86 FDI -> Mahalito |
| `nfd2mhlt.py in.nfd out` | T98-Next NFD (R0; R1 experimental) -> Mahalito |

Shared logic lives in `diskutil.py`. Run the tests with `python3 -m unittest discover -s tests -v`.
