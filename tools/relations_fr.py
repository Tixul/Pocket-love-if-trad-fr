"""Écran « Relations » (menu, page 3) : plaques de nom des filles et libellés des lignes.

Entrée 67 : u16 nombre (90) + tuiles 2 bpp ; 15 tuiles par fille (3 x 5, rangée par rangée),
ordre à l'écran : Mirei, Konoha, Ruruna, Mizuki, Yumi, Momoyo. La plaque = tuiles 9-14
(24 x 16 px, cadre gardé, zone utile x 1..21, y 1..13).
Entrée 69 : w, h (2 x 8), carte, u16 nombre (16) + tuiles : 4 libellés de 16 x 16 px
(愛情 affection, 興味 intérêt, 親密 intimité, デート rendez-vous), zone utile x 1..14, y 2..13.
Choix de Tixul (22/11) : LOVE / ÉLAN / LIEN / RDV, noms longs sur 2 lignes (RURU/NA…).
Les deux entrées sont modifiées en place (même taille).
"""
import struct

# Petites majuscules 5 px de haut, largeur variable ; 'É' a son accent sur la ligne du dessus.
P = {
    'A': [".#.", "#.#", "###", "#.#", "#.#"],
    'D': ["##.", "#.#", "#.#", "#.#", "##."],
    'E': ["###", "#..", "##.", "#..", "###"],
    'H': ["#.#", "#.#", "###", "#.#", "#.#"],
    'I': ["#", "#", "#", "#", "#"],
    'K': ["#.#", "#.#", "##.", "#.#", "#.#"],
    'L': ["#.", "#.", "#.", "#.", "##"],
    'M': ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    'N': ["#..#", "##.#", "#.##", "#..#", "#..#"],
    'O': [".#.", "#.#", "#.#", "#.#", ".#."],
    'R': ["##.", "#.#", "##.", "#.#", "#.#"],
    'U': ["#.#", "#.#", "#.#", "#.#", "###"],
    'V': ["#.#", "#.#", "#.#", "#.#", ".#."],
    'Y': ["#.#", "#.#", ".#.", ".#.", ".#."],
    'Z': ["###", "..#", ".#.", "#..", "###"],
}
ACCENT = {'É': ('E', "..#")}
# Libellés (14 px utiles) : E étroit, accent posé 2 rangs au-dessus (un rang vide entre les deux).
ETROIT = {'E': ["##", "#.", "##", "#.", "##"]}

NOMS = [['MIREI'], ['KONO', 'HA'], ['RURU', 'NA'], ['MIZUKI'], ['YUMI'], ['MOMO', 'YO']]
LIBELLES = ['LOVE', 'ÉLAN', 'LIEN', 'RDV']
ENCRE = 3


def _glyphe(c, etroit):
    base = ACCENT.get(c, (c,))[0]
    return (ETROIT if etroit and base in ETROIT else P)[base]


def largeur(mot, etroit=False):
    return sum(len(_glyphe(c, etroit)[0]) for c in mot) + len(mot) - 1


def dessine(pix, mot, x, y, etroit=False):
    for c in mot:
        g = _glyphe(c, etroit)
        if c in ACCENT:
            pix[y - 2 if etroit else y - 1][x + len(g[0]) - 1] = ENCRE
        for dy, ligne in enumerate(g):
            for dx, ch in enumerate(ligne):
                if ch == '#':
                    pix[y + dy][x + dx] = ENCRE
        x += len(g[0]) + 1


def vers_pixels(tuiles, cols, rows):
    pix = [[0] * (8 * cols) for _ in range(8 * rows)]
    for k, t in enumerate(tuiles):
        tx, ty = k % cols, k // cols
        for y in range(8):
            w = t[2 * y] | (t[2 * y + 1] << 8)
            for x in range(8):
                pix[8 * ty + y][8 * tx + x] = (w >> (14 - 2 * x)) & 3
    return pix


def vers_tuiles(pix, cols, rows):
    out = []
    for ty in range(rows):
        for tx in range(cols):
            b = bytearray()
            for y in range(8):
                w = 0
                for x in range(8):
                    w |= pix[8 * ty + y][8 * tx + x] << (14 - 2 * x)
                b += bytes([w & 255, w >> 8])
            out.append(bytes(b))
    return out


def efface(pix, x0, x1, y0, y1, fond):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            pix[y][x] = fond


def plaque(tuiles6, lignes):
    pix = vers_pixels(tuiles6, 3, 2)
    fond = pix[1][1]
    efface(pix, 1, 21, 1, 13, fond)
    haut = 5 * len(lignes) + 2 * (len(lignes) - 1)
    y = 1 + (13 - haut + 1) // 2
    for mot in lignes:
        w = largeur(mot)
        if w > 21:
            raise SystemExit('relations : %s trop large (%d px)' % (mot, w))
        dessine(pix, mot, 1 + (21 - w + 1) // 2, y)
        y += 7
    return vers_tuiles(pix, 3, 2)


def libelle(tuiles4, mot):
    pix = vers_pixels(tuiles4, 2, 2)
    fond = pix[2][1]
    w = largeur(mot, True)
    if w > 14:
        raise SystemExit('relations : %s trop large (%d px)' % (mot, w))
    efface(pix, 1, 14, 2, 13, fond)
    for y in range(2, 14):             # bord gauche ombré (2/3 mêlés) -> clair : ne colle plus au texte
        pix[y][0] = 2
    dessine(pix, mot, 1 + (14 - w + 1) // 2, 6, True)
    return vers_tuiles(pix, 2, 2)


def _entree(rom, i):
    off, taille = struct.unpack_from('<II', rom, 0x20004 + 8 * i)
    return 0x20000 + off, taille


def applique(out, rom):
    b67, _ = _entree(rom, 67)
    if struct.unpack_from('<H', rom, b67)[0] != 90:
        raise SystemExit('ROM inattendue (relations, entrée 67)')
    for g, lignes in enumerate(NOMS):
        idx = [15 * g + 9 + k for k in range(6)]
        t = [rom[b67 + 2 + 16 * k:b67 + 18 + 16 * k] for k in idx]
        for k, neuve in zip(idx, plaque(t, lignes)):
            out[b67 + 2 + 16 * k:b67 + 18 + 16 * k] = neuve
    b69, _ = _entree(rom, 69)
    w, h = rom[b69], rom[b69 + 1]
    p = b69 + 2 + 2 * w * h
    if (w, h) != (2, 8) or struct.unpack_from('<H', rom, p)[0] != 16:
        raise SystemExit('ROM inattendue (relations, entrée 69)')
    carte = [struct.unpack_from('<H', rom, b69 + 2 + 2 * k)[0] & 0x1FF for k in range(16)]
    for n, mot in enumerate(LIBELLES):
        idx = [carte[(2 * n + r) * 2 + c] for r in (0, 1) for c in (0, 1)]
        t = [rom[p + 2 + 16 * k:p + 18 + 16 * k] for k in idx]
        for k, neuve in zip(idx, libelle(t, mot)):
            out[p + 2 + 16 * k:p + 18 + 16 * k] = neuve
