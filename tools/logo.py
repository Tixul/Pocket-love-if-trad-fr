"""Logo de l'écran titre (entrée 87 : carte 20x19, tuiles 2 bpp, 8 palettes).

Format : w, h (octets), w*h mots de carte (tuile 9 bits | palette << 9 | flips << 14),
u16 nb tuiles, tuiles, puis 1 octet (nb palettes) + palettes (4 couleurs x u16 0x0BGR).

    python -I -B tools/logo.py voir ROM SORTIE.png     (rendu du plan, agrandi)
"""
import struct
import sys

from PIL import Image


def lit(rom, i=87):
    off, taille = struct.unpack_from('<II', rom, 0x20004 + 8 * i)
    b = 0x20000 + off
    w, h = rom[b], rom[b + 1]
    carte = [struct.unpack_from('<H', rom, b + 2 + 2 * k)[0] for k in range(w * h)]
    p = b + 2 + 2 * w * h
    nt = struct.unpack_from('<H', rom, p)[0]
    tuiles = [rom[p + 2 + 16 * k:p + 18 + 16 * k] for k in range(nt)]
    q = p + 2 + 16 * nt
    npal = rom[q]
    pals = [[struct.unpack_from('<H', rom, q + 1 + 8 * k + 2 * c)[0] for c in range(4)] for k in range(npal)]
    return w, h, carte, tuiles, pals


def rgb(c):
    return ((c & 15) * 17, ((c >> 4) & 15) * 17, ((c >> 8) & 15) * 17)


def pixels(t):
    return [[((t[2 * y] | (t[2 * y + 1] << 8)) >> (14 - 2 * x)) & 3 for x in range(8)] for y in range(8)]


def rendu(w, h, carte, tuiles, pals, indices=False):
    im = Image.new('RGB', (8 * w, 8 * h), (200, 230, 200))
    for k, m in enumerate(carte):
        t, pal, hf, vf = m & 0x1FF, (m >> 9) & 15, (m >> 15) & 1, (m >> 14) & 1
        px = pixels(tuiles[t]) if t < len(tuiles) else [[0] * 8] * 8
        for y in range(8):
            for x in range(8):
                v = px[7 - y if vf else y][7 - x if hf else x]
                if v:
                    im.putpixel((8 * (k % w) + x, 8 * (k // w) + y), rgb(pals[pal][v]))
    return im


if __name__ == '__main__':
    if sys.argv[1] == 'voir':
        rom = open(sys.argv[2], 'rb').read()
        im = rendu(*lit(rom))
        im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(sys.argv[3])


# ---------------------------------------------------------------- logo latin
from PIL import ImageDraw, ImageFont  # noqa: E402

POLICE = r'C:\Windows\Fonts\comicbd.ttf'


def _masque(texte, police, taille, espace=0):
    font = ImageFont.truetype(police, taille)
    pts = set()
    cx = 0
    for ch in texte:
        if ch == ' ':
            cx += taille // 3
            continue
        im = Image.new('L', (taille * 2, taille * 2), 0)
        ImageDraw.Draw(im).text((0, 0), ch, font=font, fill=255)
        g = {(x, y) for x in range(im.width) for y in range(im.height) if im.getpixel((x, y)) > 120}
        x0 = min(x for x, _ in g)
        x1 = max(x for x, _ in g)
        pts |= {(x - x0 + cx, y) for x, y in g}
        cx += x1 - x0 + 1 + espace
    y0 = min(y for _, y in pts)
    return {(x, y - y0) for x, y in pts}


def _dilate(pts, r):
    out = set(pts)
    for x, y in pts:
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                if a * a + b * b <= r * r + r:
                    out.add((x + a, y + b))
    return out


def masque_sprite(rom, i):
    """Pixels non vides d'un lettrage sprite (entrée i), origine = 1er sprite."""
    off, _ = struct.unpack_from('<II', rom, 0x20004 + 8 * i)
    b = 0x20000 + off
    n = rom[b]
    ents = [tuple(rom[b + 1 + 4 * k:b + 5 + 4 * k]) for k in range(n)]
    nt = struct.unpack_from('<H', rom, b + 1 + 5 * n)[0]
    t0 = b + 3 + 5 * n
    pts = set()
    x = y = 0
    for k, (t, f, dx, dy) in enumerate(ents):
        dx = dx - 256 if dx > 127 else dx
        dy = dy - 256 if dy > 127 else dy
        if k and f & 6:
            x, y = x + dx, y + dy
        px = pixels(rom[t0 + 16 * t:t0 + 16 * t + 16])
        for yy in range(8):
            for xx in range(8):
                if px[7 - yy if f & 0x40 else yy][7 - xx if f & 0x80 else xx]:
                    pts.add((x + xx, y + yy))
    return pts


def dessine_logo(rom, texte='Pocket Love', police=POLICE, taille=24, x=6, y=26, espace=0,
                 coeurs=((40, 24), (128, 32))):
    """-> (index[y][x], palette par tuile, palettes, conflits). coeurs = positions des sprites 89 / 93."""
    w, h, carte, tuiles, pals = lit(rom)
    W, H = 8 * w, 8 * h
    orig = [[0] * W for _ in range(H)]
    tpal = [(m >> 9) & 15 for m in carte]
    for k, m in enumerate(carte):
        t, hf, vf = m & 0x1FF, (m >> 15) & 1, (m >> 14) & 1
        px = pixels(tuiles[t])
        for yy in range(8):
            for xx in range(8):
                orig[8 * (k // w) + yy][8 * (k % w) + xx] = px[7 - yy if vf else yy][7 - xx if hf else xx]
    idx = [row[:] for row in orig]
    for b in range(8, 80):                       # tout le logo (rangées 1 à 9) est redessiné
        for a in range(W):
            idx[b][a] = 0
    pal_de = lambda a, b: tpal[(b // 8) * w + a // 8]
    # formes : (remplissage, valeur du remplissage)
    texte_px = {(a + x, b + y) for a, b in _masque(texte, police, taille, espace)}
    if_px = {(a, b) for b in range(8, 80) for a in range(W) if pal_de(a, b) != 0 and orig[b][a] == 2}
    coeur_px = set()
    for e, (cx, cy) in zip((89, 93), coeurs):
        coeur_px |= {(a + cx, b + cy) for a, b in masque_sprite(rom, e)}
    pleins = texte_px | if_px | coeur_px
    contour = _dilate(pleins, 1)
    bord = _dilate(contour, 2)
    ombre = {(a + 2, b + 2) for a, b in bord}
    conflits = []
    for couche, v in ((ombre, 3), (bord, 1), (contour, 3), (texte_px | coeur_px, 2), (if_px, 2)):
        for a, b in couche:
            if 0 <= a < W and 8 <= b < 80:
                idx[b][a] = v
    for a, b in texte_px | coeur_px:
        if 0 <= a < W and 0 <= b < H and pal_de(a, b) != 0:
            conflits.append((a, b))
    return idx, tpal, pals, conflits


def apercu(idx, tpal, pals, w=20):
    H, W = len(idx), len(idx[0])
    im = Image.new('RGB', (W, H), (200, 230, 200))
    for b in range(H):
        for a in range(W):
            v = idx[b][a]
            if v:
                im.putpixel((a, b), rgb(pals[tpal[(b // 8) * w + a // 8]][v]))
    return im


# Mise en page retenue (20/11/2026) : sprites cœurs 89 / 93 déplacés aux mêmes positions.
MISE_EN_PAGE = dict(texte='Pocket Love', x=4, y=24, taille=25, coeurs=((66, 12), (134, 28)))


def _tuile(idx, tx, ty, hf=False, vf=False):
    b = bytearray()
    for y in range(8):
        w = 0
        for x in range(8):
            v = idx[8 * ty + (7 - y if vf else y)][8 * tx + (7 - x if hf else x)]
            w |= v << (14 - 2 * x)
        b += bytes([w & 255, w >> 8])
    return bytes(b)


def entree_logo(rom):
    """-> (octets de la nouvelle entrée 87, positions des cœurs, nb de tuiles)."""
    idx, tpal, pals, conflits = dessine_logo(rom, **MISE_EN_PAGE)
    if conflits:
        raise SystemExit('logo : %d pixels roses dans une tuile d\'une autre palette' % len(conflits))
    w, h, carte, tuiles, _ = lit(rom)
    off, taille = struct.unpack_from('<II', rom, 0x20004 + 8 * 87)
    b = 0x20000 + off
    queue = rom[b + 2 + 2 * w * h + 2 + 16 * len(tuiles):b + taille]   # palettes d'origine
    neuves, index, mots = [bytes(16)], {bytes(16): 0}, []
    for ty in range(h):
        for tx in range(w):
            pal = tpal[ty * w + tx]
            t = _tuile(idx, tx, ty)
            if t == bytes(16):
                mots.append(0)
                continue
            for hf, vf in ((0, 0), (1, 0), (0, 1), (1, 1)):     # réutiliser une tuile retournée
                tt = _tuile(idx, tx, ty, hf, vf)
                if tt in index:
                    mots.append(index[tt] | pal << 9 | hf << 15 | vf << 14)
                    break
            else:
                index[t] = len(neuves)
                neuves.append(t)
                mots.append(index[t] | pal << 9)
    out = bytes([w, h]) + b''.join(struct.pack('<H', m) for m in mots)
    out += struct.pack('<H', len(neuves)) + b''.join(neuves) + queue
    return out, MISE_EN_PAGE['coeurs'], len(neuves)
