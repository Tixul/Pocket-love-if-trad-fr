"""Lettrages de l'écran titre (sprites, entrées 90/91/92 de l'archive), redessinés en français.

Format d'une entrée sprite : n (1 octet), n × (tuile, attributs, x, y), n octets de palette,
nombre de tuiles (u16), tuiles 2 bpp. Le premier sprite est placé par le jeu, les suivants
sont chaînés (attributs | 0x06, x/y relatifs au précédent). Tuiles allouées en VRAM à la suite
à partir de 234 ; 259-511 sont vides à l'écran titre, donc un lettrage peut grandir.

Style d'origine : remplissage = couleur 1, contour = 3, coins du contour = 2.

    python -I -B tools/titre_fr.py APERCU.png    (aperçu agrandi)
"""
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

POLICE = r'C:\Windows\Fonts\verdana.ttf'
TAILLE = 13
INTERLETTRE = 2     # 2 px entre deux lettres : les contours ne se touchent pas
ESPACE = 4
# entrée : (texte, centre x d'origine relatif à la position du 1er sprite, attributs 1er/suivants)
LETTRAGES = {
    90: ('Appuie sur A !', 48, 24, 30),
    91: ('Nouvelle partie', 32, 56, 62),
    92: ('Charger', 16, 56, 62),
    94: ('Album', 28, 56, 62),
}
# Table des descripteurs de l'écran titre (fichier 0x19DC8, 10 octets) :
# (entrée, tuile VRAM de départ, n° du 1er sprite, x, y). Les options du menu 91 / 92 / 94
# sont affichées ENSEMBLE : leurs tuiles et sprites sont réalloués à la suite.
DESCRIPTEURS = 0x19DC8
MENU = [(3, 91), (4, 92), (5, 94)]      # (n° de descripteur, entrée)


def dessin(texte):
    """-> image 'L' (valeurs 0..3) de hauteur 16, largeur multiple de 8."""
    font = ImageFont.truetype(POLICE, TAILLE)
    pts = set()
    cx = 2
    for ch in texte:
        if ch == ' ':
            cx += ESPACE
            continue
        im = Image.new('L', (40, 20), 0)
        ImageDraw.Draw(im).text((0, 1), ch, font=font, fill=255)
        px = im.load()
        g = {(x, y) for x in range(40) for y in range(20) if px[x, y] > 110}
        gx0 = min(x for x, _ in g)
        gx1 = max(x for x, _ in g)
        pts |= {(x - gx0 + cx, y) for x, y in g}
        cx += gx1 - gx0 + 1 + INTERLETTRE
    x0 = min(x for x, _ in pts) - 1
    y0 = min(y for _, y in pts) - 1
    y1 = max(y for _, y in pts) + 1
    h = y1 - y0 + 1
    dy = (16 - h) // 2
    w = max(x for x, _ in pts) - x0 + 2
    W = (w + 7) // 8 * 8
    out = Image.new('L', (W, 16), 0)
    o = out.load()
    for x, y in pts:
        o[x - x0, y - y0 + dy] = 1
    for x in range(W):
        for y in range(16):
            if o[x, y]:
                continue
            ortho = any(0 <= x + a < W and 0 <= y + b < 16 and o[x + a, y + b] == 1
                        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            diag = any(0 <= x + a < W and 0 <= y + b < 16 and o[x + a, y + b] == 1
                       for a, b in ((1, 1), (-1, -1), (1, -1), (-1, 1)))
            if ortho:
                o[x, y] = 9
            elif diag:
                o[x, y] = 8
    for x in range(W):
        for y in range(16):
            o[x, y] = {9: 3, 8: 2}.get(o[x, y], o[x, y])
    return out


def tuile(im, tx, ty):
    b = bytearray()
    p = im.load()
    for y in range(8):
        w = 0
        for x in range(8):
            w |= p[tx * 8 + x, ty * 8 + y] << (14 - 2 * x)
        b += bytes([w & 255, w >> 8])
    return bytes(b)


def entree(texte, centre, attr0, attr, palette):
    im = dessin(texte)
    cols = im.width // 8
    tuiles, sprites = [], []
    x_prec = y_prec = None
    depart = 0          # le jeu place le 1er sprite au x/y du descripteur (centrage : descripteurs())
    for ty in range(2):
        for tx in range(cols):
            t = tuile(im, tx, ty)
            if t == bytes(16) and x_prec is not None:   # la 1re tuile est toujours gardée (origine)
                continue
            x, y = tx * 8, ty * 8
            if x_prec is None:
                sprites.append((len(tuiles), attr0, depart, 0))
            else:
                sprites.append((len(tuiles), attr, (x - x_prec) & 0xFF, (y - y_prec) & 0xFF))
            x_prec, y_prec = x, y
            tuiles.append(t)
    b = bytearray([len(sprites)])
    for s in sprites:
        b += bytes(s)
    b += bytes([palette] * len(sprites))
    b += struct.pack('<H', len(tuiles))
    b += b''.join(tuiles)
    return bytes(b), im


def descripteurs(rom, donnees):
    """-> liste (offset fichier, 10 octets) des descripteurs du menu réalloués."""
    out = []
    tuile, sprite = None, None
    for k, e in MENU:
        a = DESCRIPTEURS + 10 * k
        ent, t0, s0, x, y = struct.unpack_from('<5H', rom, a)
        if ent != e:
            raise SystemExit('descripteur %d inattendu' % k)
        if tuile is None:
            tuile, sprite = t0, s0
        d = donnees[e]
        n = d[0]
        nt = struct.unpack_from('<H', d, 1 + 5 * n)[0]
        texte, centre = LETTRAGES[e][0], LETTRAGES[e][1]
        x = (x + centre - dessin(texte).width // 2) & 0xFFFF
        out.append((a, struct.pack('<5H', e, tuile, sprite, x, y)))
        tuile += nt
        sprite += n
    if sprite > 64 or tuile > 512:
        raise SystemExit('menu titre : %d sprites, tuile %d : trop' % (sprite, tuile))
    # « Appuie sur A » (descripteur 2, écran à part) : seulement recentré
    a = DESCRIPTEURS + 20
    e, t0, s0, x, y = struct.unpack_from('<5H', rom, a)
    texte, centre = LETTRAGES[e][0], LETTRAGES[e][1]
    out.append((a, struct.pack('<5H', e, t0, s0, (x + centre - dessin(texte).width // 2) & 0xFFFF, y)))
    return out


def entrees(rom):
    """-> {numéro d'entrée: octets}, palettes reprises de l'original."""
    out = {}
    for i, (texte, centre, a0, a) in LETTRAGES.items():
        off, taille = struct.unpack_from('<II', rom, 0x20004 + 8 * i)
        b = 0x20000 + off
        n = rom[b]
        pal = rom[b + 1 + 4 * n]
        nt = struct.unpack_from('<H', rom, b + 1 + 5 * n)[0]
        queue = rom[b + 3 + 5 * n + 16 * nt:b + taille]   # données après les tuiles (palettes) : recopiées
        out[i] = entree(texte, centre, a0, a, pal)[0] + queue
    return out


if __name__ == '__main__':
    ims = [entree(t, c, a0, a, 1)[1] for t, c, a0, a in LETTRAGES.values()]
    coul = [(255, 255, 255), (240, 90, 150), (200, 60, 110), (120, 20, 60)]
    H = 18 * len(ims)
    W = max(i.width for i in ims)
    ap = Image.new('RGB', (W, H), (255, 255, 255))
    for k, im in enumerate(ims):
        for x in range(im.width):
            for y in range(16):
                ap.putpixel((x, 18 * k + y), coul[im.getpixel((x, y))])
    ap.resize((W * 6, H * 6), Image.NEAREST).save(sys.argv[1])
    print([i.width for i in ims])
