"""Onglets du clavier de saisie du nom (sprites, entrée 50 : 48 tuiles 2 bpp, chargées en VRAM 48+).
Pastille = 3x2 tuiles (24x16) : bord 3, fond 1, ombre 2 à droite, texte 3 (lignes 4-11, colonnes 2-19).
Index de la 1re tuile de chaque pastille -> libellé.
"""
import struct

import planning_fr
import stats_fr

ONGLETS = {10: 'ABC', 16: 'Éàç', 22: '123', 28: 'JP', 34: 'Fin', 40: 'Fin'}   # ひら カタ 英数 漢字 終了 終了

EXTRA = {
    'B': ["###.", "#..#", "###.", "#..#", "#..#", "###."],
    'C': [".###", "#...", "#...", "#...", "#...", ".###"],
    'J': ["..##", "...#", "...#", "...#", "#..#", ".##."],
    'P': ["###.", "#..#", "#..#", "###.", "#...", "#..."],
    'à': ["#...", ".#..", ".##.", "...#", ".###", ".###"],
    'ç': ["....", ".###", "#...", ".###", "..#.", ".#.."],
    '1': [".#..", "##..", ".#..", ".#..", ".#..", "###."],
    '2': [".##.", "#..#", "..#.", ".#..", "#...", "####"],
    '3': ["###.", "...#", ".##.", "...#", "...#", "###."],
}


def _px(t):
    return [[((t[2 * y] | (t[2 * y + 1] << 8)) >> (14 - 2 * x)) & 3 for x in range(8)] for y in range(8)]


def _tuile(px):
    b = bytearray()
    for y in range(8):
        w = 0
        for x in range(8):
            w |= px[y][x] << (14 - 2 * x)
        b += bytes([w & 255, w >> 8])
    return bytes(b)


def applique(out, rom):
    F = dict(planning_fr.F)
    F.update(stats_fr.EXTRA)
    F.update(EXTRA)
    off = struct.unpack_from('<I', rom, 0x20004 + 8 * 50)[0]
    b = 0x20000 + off + 2
    for base, texte in ONGLETS.items():
        img = [[0] * 24 for _ in range(16)]
        for row in range(2):
            for c in range(3):
                px = _px(rom[b + 16 * (base + 3 * row + c):b + 16 * (base + 3 * row + c) + 16])
                for y in range(8):
                    for x in range(8):
                        img[8 * row + y][8 * c + x] = px[y][x]
        for y in range(4, 12):                 # intérieur nettoyé (fond 1), ombre de droite gardée
            for x in range(1, 20):
                img[y][x] = 1
        larg = 5 * len(texte) - 1
        ox = 2 + (18 - larg) // 2
        for i, ch in enumerate(texte):
            g = F[ch]
            for yy in range(6):
                for xx in range(4):
                    if g[yy][xx] == '#':
                        img[5 + yy][ox + 5 * i + xx] = 3
        for row in range(2):
            for c in range(3):
                t = _tuile([img[8 * row + y][8 * c:8 * c + 8] for y in range(8)])
                a = b + 16 * (base + 3 * row + c)
                out[a:a + 16] = t
