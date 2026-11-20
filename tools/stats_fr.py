"""Libellés des stats (écran de planning) : entrée 52 = carte 4x9 (palette 10) + tuiles + palettes.
Six bandes de 32x12 px, couleur 1 / 2 en alternance ; texte = 0 (blanc, transparent) cerné de 3 (noir).
"""
import struct

import planning_fr

# 学力 容姿 体力 器用さ 健康 センス. Place réservée en VRAM : 34 tuiles (E2-E3 servent ailleurs en même
# temps) ; les tuiles en trop vont dans les cases libres de la petite police du planning (entrée 55,
# chargée sur le même écran) : sub_215499 calcule (index + 0xC0) & 0x1FF, donc une case peut viser
# n'importe quelle tuile VRAM.
LIBELLES = ['Études', 'Look', 'Forme', 'Talent', 'Santé', 'Goût']
# Look et Goût (même couleur de bande) calés à gauche : leur dernière colonne = même tuile unie (-1 tuile)
A_GAUCHE = {1, 5}

# lettres manquant à la police 4x6 du planning
EXTRA = {
    'É': ["..#.", "####", "#...", "###.", "#...", "####"],
    'L': ["#...", "#...", "#...", "#...", "#...", "####"],
    'T': ["####", ".#..", ".#..", ".#..", ".#..", ".#.."],
    'F': ["####", "#...", "###.", "#...", "#...", "#..."],
    'D': ["###.", "#..#", "#..#", "#..#", "#..#", "###."],
    'S': [".###", "#...", ".##.", "...#", "...#", "###."],
    'k': ["#...", "#...", "#..#", "###.", "#..#", "#..#"],
    'g': ["....", ".###", "#..#", ".###", "...#", ".##."],
    'é': ["..#.", ".#..", ".##.", "####", "#...", ".###"],
    's': ["....", ".###", "#...", ".##.", "...#", "###."],
    'G': [".###", "#...", "#.##", "#..#", "#..#", ".###"],
    'û': [".#..", "#.#.", "....", "#..#", "#..#", ".###"],
    'y': ["....", "#..#", "#..#", ".###", "...#", ".##."],
    'l': ["##..", ".#..", ".#..", ".#..", ".#..", ".##."],
}


def image():
    F = dict(planning_fr.F)
    F.update(EXTRA)
    W, H = 32, 72
    px = [[0] * W for _ in range(H)]
    for i, texte in enumerate(LIBELLES):
        y0 = 12 * i
        fond = 1 if i % 2 == 0 else 2
        for y in range(y0, y0 + 12):
            for x in range(W):
                px[y][x] = fond
        pts = set()
        cx = 0
        for ch in texte:
            g = F[ch]
            for yy in range(6):
                for xx in range(4):
                    if g[yy][xx] == '#':
                        pts.add((cx + xx, yy))
            cx += 5
        larg = cx - 1
        ox = 1 if i in A_GAUCHE else (W - larg) // 2
        oy = y0 + 3
        if larg > W - 2:
            raise SystemExit('stats : « %s » trop large (%d px)' % (texte, larg))
        pts = {(x + ox, y + oy) for x, y in pts}
        for x, y in pts:                       # contour noir
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    if 0 <= x + a < W and y0 <= y + b < y0 + 12:
                        px[y + b][x + a] = 3
        for x, y in pts:                       # lettre blanche (transparente)
            px[y][x] = 0
    return px


def entree(rom, libres, out):
    off, taille = struct.unpack_from('<II', rom, 0x20004 + 8 * 52)
    b = 0x20000 + off
    w, h = rom[b], rom[b + 1]
    mot0 = struct.unpack_from('<H', rom, b + 2)[0]
    attr = mot0 & 0xFE00
    p = b + 2 + 2 * w * h
    nt = struct.unpack_from('<H', rom, p)[0]
    queue = rom[p + 2 + 16 * nt:b + taille]
    px = image()
    tuiles, index, mots = [], {}, []
    for ty in range(h):
        for tx in range(w):
            t = bytearray()
            for y in range(8):
                v = 0
                for x in range(8):
                    v |= px[8 * ty + y][8 * tx + x] << (14 - 2 * x)
                t += bytes([v & 255, v >> 8])
            t = bytes(t)
            if t not in index:
                index[t] = len(tuiles)
                tuiles.append(t)
            mots.append(index[t] | attr)
    base_vram = 0xC0
    if len(tuiles) > nt:
        trop = len(tuiles) - nt
        if trop > len(libres):
            raise SystemExit('stats : %d tuiles en trop, %d cases libres' % (trop, len(libres)))
        for k in range(trop):
            vram, adr = libres[k]
            out[adr:adr + 16] = tuiles[nt + k]
            ancien = nt + k
            neuf = (vram - base_vram) & 0x1FF
            mots = [(m & ~0x1FF) | neuf if (m & 0x1FF) == ancien else m for m in mots]
        tuiles = tuiles[:nt]
    tuiles += [bytes(16)] * (nt - len(tuiles))
    return (bytes([w, h]) + b''.join(struct.pack('<H', m) for m in mots)
            + struct.pack('<H', nt) + b''.join(tuiles) + queue)
