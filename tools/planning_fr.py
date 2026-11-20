"""Écran de planning : libellés et aides, dessinés avec la petite police de l'entrée 55 (tuiles VRAM
0x30-0x4F) par sub_215499 à partir de petites cartes en ROM (w, h, puis w*h mots tuile|pal<<9).

On remplace les 32 glyphes de l'entrée 55 par des morceaux de phrases françaises (police 4x6,
avance 5 px) et on réécrit les cartes :
  semaine  : libellés « À fond = » / « Un peu = » ; aide « [J] : quoi / faire / À fond ? »
  week-end : libellés « Matin = » / « Aprèm = » ; aide « Matin : / que faire ? »
Les cartes qui grandissent (Matin / Aprèm : 1 → 3 tuiles) vont sur la puce 2 ; les pointeurs
(pushw / ld XWA,imm) et la colonne des libellés du week-end (6 → 4) sont patchés.
"""
import struct

PAL = 0x1C00          # palette 14, comme les cartes d'origine
# ⛔ cases de l'entrée 55 GARDÉES d'origine (vu cassé le 20/11) : 28-31 = main-curseur (sprites 42-45,
# menu « Appeler »), 21-22 = ◁ ▷ (pages de la boutique), 13 = ？ (réutilisé tel quel pour « ? »).
GARDEES = {13, 21, 22, 28, 29, 30, 31}
POINT = 0x30 + 13          # ？ d'origine
DEUX_POINTS = 0x1C         # « ・ » de la police du bandeau (entrée 39), redessiné en « : » par hud_fr
BASE = 0x30           # 1re tuile VRAM de l'entrée 55

# police 4x6 (6 lignes, de la ligne 1 à la ligne 6 de la tuile ; '#' = trait), avance 5 px
F = {
    'A': [".##.", "#..#", "#..#", "####", "#..#", "#..#"],
    'À': ["#...", ".##.", "#..#", "####", "#..#", "#..#"],
    'M': ["#..#", "####", "####", "#..#", "#..#", "#..#"],
    'U': ["#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    'a': ["....", ".##.", "...#", ".###", "#..#", ".###"],
    'd': ["...#", "...#", ".###", "#..#", "#..#", ".###"],
    'e': ["....", ".##.", "#..#", "####", "#...", ".###"],
    'è': ["#...", ".#..", ".##.", "####", "#...", ".###"],
    'f': ["..##", ".#..", "####", ".#..", ".#..", ".#.."],
    'i': [".#..", "....", ".#..", ".#..", ".#..", ".#.."],
    'm': ["....", "#.#.", "####", "#.#.", "#.#.", "#.#."],
    'n': ["....", "###.", "#..#", "#..#", "#..#", "#..#"],
    'o': ["....", ".##.", "#..#", "#..#", "#..#", ".##."],
    'p': ["....", "###.", "#..#", "###.", "#...", "#..."],
    'q': ["....", ".###", "#..#", ".###", "...#", "...#"],
    'r': ["....", "#.#.", "##..", "#...", "#...", "#..."],
    't': [".#..", ".#..", "####", ".#..", ".#..", "..##"],
    'u': ["....", "#..#", "#..#", "#..#", "#..#", ".###"],
    ':': ["....", ".#..", "....", "....", ".#..", "...."],
    'R': ["###.", "#..#", "#..#", "###.", "#.#.", "#..#"],
    'P': ["###.", "#..#", "#..#", "###.", "#...", "#..."],
    's': ["....", ".###", "#...", ".##.", "...#", "###."],
    'x': ["....", "#..#", ".##.", ".##.", ".##.", "#..#"],
    '?': [".##.", "#..#", "..#.", ".#..", "....", ".#.."],
    ' ': ["....", "....", "....", "....", "....", "...."],
}


def bande(texte, largeur, droite=False):
    """-> liste de colonnes de pixels (largeur px), texte calé à gauche ou à droite."""
    cols = []
    for ch in texte:
        g = F[ch]
        if ch == ' ':
            cols += [[False] * 6] * 3
            continue
        xs = [x for x in range(4) if any(g[y][x] == '#' for y in range(6))]
        for x in range(min(xs), max(xs) + 1):     # chasse proportionnelle : colonnes vides rognées
            cols.append([g[y][x] == '#' for y in range(6)])
        cols.append([False] * 6)
    cols = cols[:-1] if cols else cols
    if len(cols) > largeur:
        raise SystemExit('planning : « %s » trop long (%d px > %d)' % (texte, len(cols), largeur))
    vide = [[False] * 6] * (largeur - len(cols))
    return (vide + cols) if droite else (cols + vide)


def tuiles_de(cols, encre):
    out = []
    for t in range(len(cols) // 8):
        b = bytearray(2)                       # ligne 0 vide
        for y in range(6):
            w = 0
            for x in range(8):
                if cols[8 * t + x][y]:
                    w |= encre << (14 - 2 * x)
            b += bytes([w & 255, w >> 8])
        b += bytes(2)                          # ligne 7 vide
        out.append(bytes(b))
    return out


# (nom, texte, nb de tuiles, calé à droite)
BANDES = [
    ('afond', 'À fond', 7, True),     # 219552 : libellé ligne 5 (col 0-6) et aide ligne 17 (col 10-16)
    ('unpeu', 'Un peu', 4, True),     # 219564 : libellé ligne 7 (col 3-6) et aide ligne 17 (col 10-13)
    ('faire', 'faire', 5, False),     # 219578 ligne 2 ; aussi dans « que faire ? » (3 tuiles de texte)
    ('matin', 'Matin', 3, False),     # 219604 (déplacée, w3)
    ('aprem', 'Aprèm', 3, False),     # 219608 (déplacée, w3)
    ('que', 'que', 2, False),
    ('reste', 'Reste', 3, True),      # 219A5E boutique : のこり（argent restant）
    ('prix', 'Prix', 3, True),        # 219A5E boutique : 価格         # 2195E2 ligne 2 = « que » + tuiles de « faire » + « ? »
]


def construit(rom):
    """-> (32 tuiles de l'entrée 55, {nom: [indices de tuiles VRAM]})."""
    off = struct.unpack_from('<I', rom, 0x20004 + 8 * 55)[0]
    b = 0x20000 + off
    anciens = [rom[b + 2 + 16 * k:b + 18 + 16 * k] for k in range(32)]
    # encre = valeur de pixel la plus fréquente des glyphes d'origine
    compte = [0] * 4
    for t in anciens:
        for y in range(8):
            w = t[2 * y] | (t[2 * y + 1] << 8)
            for x in range(8):
                compte[(w >> (14 - 2 * x)) & 3] += 1
    encre = max((1, 2, 3), key=lambda v: compte[v])
    # les cases vides visent la tuile VRAM 0 (vide, police du bandeau) : pas de case perdue ici
    tuiles, index, places = [], {}, {}
    for nom, texte, n, droite in BANDES:
        idx = []
        for t in tuiles_de(bande(texte, 8 * n, droite), encre):
            if t == bytes(16):
                idx.append(0)
                continue
            if t not in index:
                index[t] = len(tuiles)
                tuiles.append(t)
            idx.append(BASE + index[t])
        places[nom] = idx
    cases = [k for k in range(32) if k not in GARDEES]
    if len(tuiles) > len(cases):
        raise SystemExit('planning : %d tuiles > %d cases' % (len(tuiles), len(cases)))
    global NB_UTILISEES, CASES
    NB_UTILISEES, CASES = len(tuiles), cases
    final = list(anciens)                       # cases gardées : tuiles d'origine
    for k in cases:
        final[k] = bytes(16)
    for i, t in enumerate(tuiles):
        final[cases[i]] = t
    places = {nom: [BASE + cases[v - BASE] if v else 0 for v in idx] for nom, idx in places.items()}
    places['point'] = [POINT]
    places['deux'] = [DEUX_POINTS]
    return final, places


NB_UTILISEES = None
CASES = None


def cases_libres(rom):
    """Cases de l'entrée 55 laissées vides par le planning (même écran) : [(tuile VRAM, offset fichier)]."""
    construit(rom)
    off = struct.unpack_from('<I', rom, 0x20004 + 8 * 55)[0]
    b = 0x20000 + off + 2
    return [(BASE + k, b + 16 * k) for k in CASES[NB_UTILISEES:]]


def carte(w, h, idx):
    # toutes les cases portent la palette (la lettre du jour est posée par le jeu dans la 1re case
    # en ne changeant que l'octet bas : sans palette, elle sortait délavée)
    return bytes([w, h]) + b''.join(struct.pack('<H', i | PAL) for i in idx)


def applique(out, rom, pos_puce2, cpu_puce2):
    """Écrit les tuiles, les cartes (en place ou sur la puce 2) et les patchs. -> nouvelle position puce 2."""
    tuiles, p = construit(rom)
    off = struct.unpack_from('<I', rom, 0x20004 + 8 * 55)[0]
    b = 0x20000 + off
    for k, t in enumerate(tuiles):
        out[b + 2 + 16 * k:b + 18 + 16 * k] = t

    def en_place(a, w, h, idx):
        if out[a] != w or out[a + 1] != h:
            raise SystemExit('planning : carte 0x%06X inattendue' % (0x200000 + a))
        out[a:a + 2 + 2 * w * h] = carte(w, h, idx)

    en_place(0x19552, 7, 1, p['afond'])
    en_place(0x19564, 4, 1, p['unpeu'])
    en_place(0x19574, 1, 1, p['point'])
    # semaine : « [J] : que / faire / À fond ? » (réutilise « : » et « que » du week-end : budget de tuiles)
    en_place(0x19578, 5, 2, [0] + p['deux'] + p['que'] + [0] + p['faire'])
    # « que faire? » réutilise les tuiles de « faire » (3 tuiles de texte) et de « ? »
    # « que » + case vide (l'espace) + « faire » + « ? » : sans tuile neuve (budget : 28 cases, 4 = main)
    quefaire = p['que'] + [0] + p['faire'][:3] + p['point'] + [0] * 1
    # boutique : « Reste = … ¥ » / « Prix = … ¥ » (= et ¥ : tuiles d'origine 0x1A et 0x1F)
    en_place(0x19A5E, 11, 2, p['reste'] + [0x1A] + [0] * 6 + [0x1F] + p['prix'] + [0x1A] + [0] * 6 + [0x1F])
    en_place(0x195E2, 8, 2, [0, 0, 0] + p['deux'] + [0] * 4 + quefaire)
    # Matin / Aprèm : cartes de 3 tuiles sur la puce 2
    nouvelles = {}
    for nom, ancien in (('matin', 0x219604), ('aprem', 0x219608)):
        d = carte(3, 1, p[nom])
        out[pos_puce2:pos_puce2 + len(d)] = d
        nouvelles[ancien] = cpu_puce2 + (pos_puce2 - 0x200000)
        pos_puce2 += (len(d) + 15) & ~15
    patchs = []
    for ancien, neuf in nouvelles.items():
        lo_a, hi_a = ancien & 0xFFFF, ancien >> 16
        lo_n, hi_n = neuf & 0xFFFF, neuf >> 16
        # pushw 0x0021 ; pushw lo  (libellés du week-end)
        avant = bytes([0x0B]) + struct.pack('<H', hi_a) + bytes([0x0B]) + struct.pack('<H', lo_a)
        apres = bytes([0x0B]) + struct.pack('<H', hi_n) + bytes([0x0B]) + struct.pack('<H', lo_n)
        patchs.append((avant, apres))
        # ld XWA,imm32 (aide du week-end)
        patchs.append((bytes([0x40]) + struct.pack('<I', ancien), bytes([0x40]) + struct.pack('<I', neuf)))
    zone = slice(0x7300, 0x73D8)
    bloc = bytes(out[zone])
    for avant, apres in patchs:
        if bloc.count(avant) != 1:
            raise SystemExit('planning : motif de patch introuvable ou multiple')
        bloc = bloc.replace(avant, apres)
    # libellés du week-end : colonne 6 -> 4 (3 tuiles qui finissent avant le « = » de la colonne 7)
    for a in (0x7306, 0x7341):
        if bloc[a - 0x7300:a - 0x7300 + 3] != bytes.fromhex('0b0600'):
            raise SystemExit('planning : colonne du libellé inattendue (0x%06X)' % (0x200000 + a))
        bloc = bloc[:a - 0x7300 + 1] + b'\x04' + bloc[a - 0x7300 + 2:]
    out[zone] = bloc
    return pos_puce2
