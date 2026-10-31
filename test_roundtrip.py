"""End-to-end tests using synthetic disk images (no real images needed).

Run with:  python3 -m unittest discover -s tests -v
"""
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(script, *args, cwd, stdout_to=None):
    cmd = [sys.executable, os.path.join(ROOT, script), *args]
    kw = dict(cwd=cwd, stderr=subprocess.PIPE)
    if stdout_to:
        with open(os.path.join(cwd, stdout_to), "wb") as out:
            return subprocess.run(cmd, stdout=out, **kw)
    return subprocess.run(cmd, stdout=subprocess.PIPE, **kw)


def make_d88(title, ncyl=2, secsize_n=1, type_byte=0x10, seed=1):
    """Build a D88 image: ncyl*2 tracks, 4 sectors each; some sectors uniform, one DDAM."""
    rnd = random.Random(seed)
    size = 128 << secsize_n
    tracks = bytearray()
    offsets = []
    base = 0x2B0
    for t in range(ncyl * 2):
        offsets.append(base + len(tracks))
        for s in range(4):
            payload = bytes([0xE5]) * size if s % 2 == 0 else bytes(rnd.randrange(256) for _ in range(size))
            deleted = 0x10 if (t == 1 and s == 3) else 0x00
            tracks += struct.pack("<BBBBHBBB5xH", t // 2, t & 1, s + 1, secsize_n, 4,
                                  0x00, deleted, 0, size) + payload
    offsets += [0] * (164 - len(offsets))
    hdr = struct.pack("<17s9xBBI", title.encode(), 0, type_byte, 0x2B0 + len(tracks))
    return hdr + struct.pack("<164I", *offsets) + bytes(tracks)


class Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.d, name)

    def read(self, name):
        with open(self.path(name), "rb") as f:
            return f.read()

    def write(self, name, data):
        with open(self.path(name), "wb") as f:
            f.write(data)

    # ---- d88split ---------------------------------------------------------
    def test_list_and_extract(self):
        a, b = make_d88("Disk_A", seed=1), make_d88("Disk_B", seed=2, type_byte=0x20)
        self.write("multi.d77", a + b)
        r = run("d88split.py", "l", "multi.d77", cwd=self.d)
        out = r.stdout.decode().splitlines()
        self.assertEqual(r.returncode, 0)
        self.assertIn("Disk_A", out[0]); self.assertIn("2DD", out[0]); self.assertIn(str(len(a)), out[0])
        self.assertIn("Disk_B", out[1]); self.assertIn("2HD", out[1])
        r = run("d88split.py", "e", "multi.d77", cwd=self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("multi#1.d77"), a)
        self.assertEqual(self.read("multi#2.d77"), b)

    def test_usage_and_missing_file(self):
        self.assertEqual(run("d88split.py", cwd=self.d).returncode, 1)
        self.assertEqual(run("d88split.py", "l", "nope.d88", cwd=self.d).returncode, 1)

    # ---- d88 <-> mahalito -------------------------------------------------
    def test_d88_mhlt_d88_roundtrip(self):
        for typ, ext in ((0x00, "2d"), (0x10, "2dd"), (0x20, "2hd")):
            with self.subTest(ext=ext):
                orig = make_d88("img", type_byte=typ)
                self.write("img.d88", orig)
                self.assertEqual(run("d882mhlt.py", "img.d88", "img", cwd=self.d).returncode, 0)
                self.assertTrue(os.path.exists(self.path(f"img.{ext}")))
                r = run("mhlt2d88.py", f"img.{ext}", cwd=self.d, stdout_to="back.d88")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.read("back.d88"), orig)   # includes DDAM sector
                os.remove(self.path(f"img.{ext}"))

    def test_concatenated_d88_naming(self):
        self.write("two.d88", make_d88("one", seed=1) + make_d88("two", seed=2))
        self.assertEqual(run("d882mhlt.py", "two.d88", "ko", cwd=self.d).returncode, 0)
        for n in (1, 2):
            self.assertTrue(os.path.exists(self.path(f"ko#{n}.2dd")))
            self.assertTrue(os.path.exists(self.path(f"ko#{n}.dat")))

    def test_flatten(self):
        orig = make_d88("img")
        self.write("img.d88", orig)
        run("d882mhlt.py", "img.d88", "img", cwd=self.d)
        self.assertEqual(run("flatmhlt.py", "img.2dd", "flat", cwd=self.d).returncode, 0)
        sectors = 2 * 2 * 4
        self.assertEqual(len(self.read("flat.dat")), sectors * 256)       # fully expanded
        self.assertLess(len(self.read("img.dat")), len(self.read("flat.dat")))
        run("mhlt2d88.py", "flat.2dd", cwd=self.d, stdout_to="flat.d88")
        # titles differ ("flat" vs "img"); everything after the 17-byte title must match
        self.assertEqual(self.read("flat.d88")[17:], orig[17:])

    def test_flatten_refuses_to_clobber_input(self):
        self.write("img.d88", make_d88("img"))
        run("d882mhlt.py", "img.d88", "img", cwd=self.d)
        before = self.read("img.dat")
        self.assertEqual(run("flatmhlt.py", "img.2dd", "img", cwd=self.d).returncode, 1)
        self.assertEqual(self.read("img.dat"), before)

    def test_not_a_mahalito_image(self):
        self.write("bad.2dd", b"garbage garbage")
        self.write("bad.dat", b"")
        self.assertEqual(run("mhlt2d88.py", "bad.2dd", cwd=self.d, stdout_to="x.d88").returncode, 1)

    # ---- XDF / FDI / NFD --------------------------------------------------
    def check_mhlt(self, meta, ncyl, ntrk, nsec, n):
        m = self.read(meta)
        self.assertEqual(m[10], ncyl)
        pos = 11
        for _ in range(ntrk):
            self.assertEqual((m[pos], m[pos + 1]), (nsec, 1))
            pos += 2
            for s in range(nsec):
                repp, repd, c, h, r, slen, rslen, ddam = m[pos:pos + 8]
                self.assertEqual((r, slen, rslen, ddam), (s + 1, n, n, 0))
                pos += 8
        self.assertEqual(pos, len(m))

    def test_xdf(self):
        body = b"".join(bytes([0xE5]) * 1024 if i % 3 == 0 else os.urandom(1024) for i in range(4 * 8))
        self.write("t.xdf", body)
        self.assertEqual(run("xdf2mhlt.py", "t.xdf", "t", cwd=self.d).returncode, 0)
        self.check_mhlt("t.2hd", ncyl=2, ntrk=4, nsec=8, n=3)
        run("mhlt2d88.py", "t.2hd", cwd=self.d, stdout_to="t.d88")
        d88 = self.read("t.d88")
        self.assertEqual(d88[0x2B0 + 16:0x2B0 + 16 + 1024], body[:1024])

    def test_fdi(self):
        hdr = struct.pack("<8I", 0, 0x90, 0x1000, 4 * 8 * 1024, 1024, 8, 2, 2).ljust(0x1000, b"\0")
        body = os.urandom(4 * 8 * 1024)
        self.write("t.fdi", hdr + body)
        r = run("fdi2mhlt.py", "t.fdi", "t", cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.check_mhlt("t.2hd", ncyl=2, ntrk=4, nsec=8, n=3)

    def test_nfd_r0(self):
        nsec_per_trk, ntrk = 8, 4
        trkinfo = bytearray()
        for t in range(163):
            for s in range(26):
                if t < ntrk and s < nsec_per_trk:
                    trkinfo += bytes([t // 2, t & 1, s + 1, 3, 1, 0, 0, 0, 0, 0, 0x90]) + bytes(5)
                else:
                    trkinfo += b"\xff" * 16
        hdr_sz = 0x120 + len(trkinfo)
        head = struct.pack("<15sx256sIBB", b"T98FDDIMAGE.R0\0", b"", hdr_sz, 0, 2).ljust(0x120, b"\0")
        self.write("t.nfd", head + bytes(trkinfo) + os.urandom(ntrk * nsec_per_trk * 1024))
        r = run("nfd2mhlt.py", "t.nfd", "t", cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.check_mhlt("t.2hd", ncyl=2, ntrk=4, nsec=8, n=3)

    def test_nfd_bad_magic(self):
        self.write("bad.nfd", bytes(0x200))
        self.assertEqual(run("nfd2mhlt.py", "bad.nfd", "x", cwd=self.d).returncode, 1)


if __name__ == "__main__":
    unittest.main()
