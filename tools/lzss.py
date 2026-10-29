#!/usr/bin/env python3
"""Glitches an image by compressing its pixels with Touhou 6's LZSS, damaging
the compressed data, and decompressing it again.

The format is the one th06's DatArchive::Decode reads, MSB first:

    1 + 8 bits         a literal byte
    0 + 13 + 4 bits    copy length + 3 bytes from that position of the
                       0x2000-byte dictionary (absolute, not a distance);
                       every output byte is also written to the dictionary,
                       starting at position 1
    0 + 13 zero bits   the end

Damage happens either to the tokens or to the bit stream itself:

    offset   a back-reference copies from somewhere nearby instead: smears
             and stutters, the rest of the image stays put
    length   a back-reference copies more or fewer bytes: everything after it
             shifts, so rows tear sideways from that point on
    literal  a literal byte changes: speckles
    bits     random bits of the stream flip: the decoder loses track of the
             token boundaries, which is the real thing, and the most chaotic

The decoder is lenient like the original (it reads zeros past the end) and
the output is cut or padded to the image's size.

    lzss.py IN OUT [--mode offset|length|literal|bits] [--count N] [--seed S]
                   [--width W] [--gray] [--from F] [--to T]
    lzss.py --test
"""
import argparse
import random
import sys

from PIL import Image

DICT_SIZE = 0x2000
MIN_MATCH, MAX_MATCH = 3, 18
# How far back a match may start: the copy writes up to MAX_MATCH bytes ahead
# of the source, so keep clear of the ring buffer wrapping onto it.
MAX_BACK = DICT_SIZE - MAX_MATCH - 1
CHAIN = 48  # candidates tried per position


def encode_tokens(data):
    """Greedy LZSS: a list of ("lit", byte) and ("ref", position, length)."""
    tokens = []
    heads = {}  # 3-byte key -> recent starting indices, newest last
    n = len(data)
    k = 0
    while k < n:
        best_len, best_src = 0, 0
        if k + MIN_MATCH <= n:
            for j in reversed(heads.get(data[k:k + MIN_MATCH], ())):
                if k - j > MAX_BACK:
                    break
                if (j + 1) % DICT_SIZE == 0:
                    continue  # position 0 means the end
                length = 0
                while length < MAX_MATCH and k + length < n and data[j + length] == data[k + length]:
                    length += 1
                if length > best_len:
                    best_len, best_src = length, j
                    if length == MAX_MATCH:
                        break
        step = best_len if best_len >= MIN_MATCH else 1
        if best_len >= MIN_MATCH:
            tokens.append(("ref", (best_src + 1) % DICT_SIZE, best_len))
        else:
            tokens.append(("lit", data[k]))
        for i in range(k, k + step):
            if i + MIN_MATCH <= n:
                chain = heads.setdefault(data[i:i + MIN_MATCH], [])
                chain.append(i)
                if len(chain) > CHAIN:
                    del chain[0]
        k += step
    return tokens


class BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.cur = 0
        self.mask = 0x80

    def bits(self, value, count):
        for i in range(count - 1, -1, -1):
            if value >> i & 1:
                self.cur |= self.mask
            self.mask >>= 1
            if not self.mask:
                self.out.append(self.cur)
                self.cur, self.mask = 0, 0x80

    def finish(self):
        if self.mask != 0x80:
            self.out.append(self.cur)
        return bytes(self.out)


def pack(tokens):
    w = BitWriter()
    for t in tokens:
        if t[0] == "lit":
            w.bits(1, 1)
            w.bits(t[1], 8)
        else:
            w.bits(0, 1)
            w.bits(t[1], 13)
            w.bits(t[2] - MIN_MATCH, 4)
    w.bits(0, 1 + 13)
    return w.finish()


def decode(stream, size):
    """DatArchive::Decode's loop, minus the checksum, stopping at `size`."""
    out = bytearray()
    dictionary = bytearray(DICT_SIZE)
    pos = 1
    bit_index = 0
    total_bits = len(stream) * 8

    def read(count):
        nonlocal bit_index
        value = 0
        for _ in range(count):
            bit = 0
            if bit_index < total_bits:
                bit = stream[bit_index >> 3] >> (7 - (bit_index & 7)) & 1
            bit_index += 1
            value = value << 1 | bit
        return value

    while len(out) < size and bit_index < total_bits:
        if read(1):
            c = read(8)
            out.append(c)
            dictionary[pos] = c
            pos = (pos + 1) % DICT_SIZE
        else:
            offset = read(13)
            if offset == 0:
                break
            for i in range(read(4) + MIN_MATCH):
                c = dictionary[(offset + i) % DICT_SIZE]
                out.append(c)
                dictionary[pos] = c
                pos = (pos + 1) % DICT_SIZE
    out = out[:size]
    return bytes(out) + bytes(size - len(out))


def corrupt(tokens, stream, mode, count, rng, lo, hi):
    """Damages `count` tokens (or, for "bits", bits of `stream`) between the
    fractions `lo` and `hi` of the data. Returns the stream to decode."""
    if mode == "bits":
        data = bytearray(stream)
        span = len(data) * 8
        for _ in range(count):
            b = rng.randrange(int(span * lo), max(int(span * lo) + 1, int(span * hi)))
            data[b >> 3] ^= 0x80 >> (b & 7)
        return bytes(data)
    tokens = list(tokens)
    kind = "lit" if mode == "literal" else "ref"
    first, last = int(len(tokens) * lo), int(len(tokens) * hi)
    candidates = [i for i in range(first, last) if tokens[i][0] == kind]
    for i in rng.sample(candidates, min(count, len(candidates))):
        t = tokens[i]
        if mode == "literal":
            tokens[i] = ("lit", rng.randrange(256))
        elif mode == "length":
            tokens[i] = ("ref", t[1], rng.randrange(MIN_MATCH, MAX_MATCH + 1))
        else:
            shifted = (t[1] + rng.choice((-1, 1)) * rng.randrange(1, 512)) % DICT_SIZE
            tokens[i] = ("ref", shifted or 1, t[2])
    return pack(tokens)


def glitch(img, mode, count, seed, gray, lo=0.0, hi=1.0):
    img = img.convert("L" if gray else "RGB")
    data = img.tobytes()
    tokens = encode_tokens(data)
    stream = corrupt(tokens, pack(tokens), mode, count, random.Random(seed), lo, hi)
    return Image.frombytes(img.mode, img.size, decode(stream, len(data)))


def test():
    rng = random.Random(1)
    samples = [
        b"",
        b"a",
        b"abcabcabcabcabcabcabcabcabc" * 50,
        bytes(rng.randrange(4) for _ in range(30000)),
        bytes(rng.randrange(256) for _ in range(20000)),
        bytes(30000),
    ]
    for data in samples:
        tokens = encode_tokens(data)
        assert decode(pack(tokens), len(data)) == data, len(data)
        print(f"ok  {len(data):6} bytes -> {len(pack(tokens)):6}")


def main():
    if sys.argv[1:] == ["--test"]:
        return test()
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--mode", choices=("offset", "length", "literal", "bits"), default="offset")
    p.add_argument("--count", type=int, default=40)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--width", type=int, help="downscale to this width first")
    p.add_argument("--gray", action="store_true", help="work on luma only")
    p.add_argument("--from", dest="lo", type=float, default=0.0, help="damage from this fraction on")
    p.add_argument("--to", dest="hi", type=float, default=1.0, help="damage up to this fraction")
    a = p.parse_args()
    img = Image.open(a.input)
    if a.width and img.width > a.width:
        img = img.resize((a.width, round(img.height * a.width / img.width)), Image.LANCZOS)
    glitch(img, a.mode, a.count, a.seed, a.gray, a.lo, a.hi).save(a.output)


if __name__ == "__main__":
    main()
