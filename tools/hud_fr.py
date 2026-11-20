"""Bandeau du haut (date) et jours de la semaine (décision Tixul : UNE lettre).

Police du bandeau = entrée 39 (tuiles 2 bpp, tuile VRAM = index) : 1-10 chiffres, 12-18 日月火水木金土,
19 « ( », 20 « ) », 29 « / », 31 円. Les jours (12-18) servent aussi à l'en-tête du planning.

Date : routine 0x203F0D-0x203FB7 écrit mois, 月, jour, 日, (, jour, ). Patch -> « 10/04 (S) » :
jour d'abord (échange des variables XSP+6 / XSP+4), « / » à la place de 月, rien à la place de 日,
dizaines toujours écrites (zéro devant).
"""
import struct

# Lettres en gras, style des « A » / « B » de la police (3 = trait, 2 = coin adouci). 7 lignes sous une ligne vide.
LETTRES = {
    'D': ["33332...", "33..32..", "33...33.", "33...33.", "33...33.", "33..32..", "33332..."],
    'L': ["33......", "33......", "33......", "33......", "33......", "33......", "3333333."],
    'M': ["33...33.", "333.333.", "3333333.", "33.3.33.", "33...33.", "33...33.", "33...33."],
    'J': ["....33..", "....33..", "....33..", "....33..", "33..33..", "33..33..", ".2332..."],
    'V': ["33...33.", "33...33.", "33...33.", "233.332.", ".33.33..", ".23332..", "..333..."],
    'S': [".23332..", "33...3..", "2332....", ".23332..", "...2332.", "3...33..", ".23332.."],
}
# 円 (tuile 31) -> ¥
YEN = ["33...33.", ".33.33..", "..333...", "3333333.", "...3....", "3333333.", "...3...."]
# index de tuile -> lettre (日 dimanche … 土 samedi)
JOURS = {12: 'D', 13: 'L', 14: 'M', 15: 'M', 16: 'J', 17: 'V', 18: 'S'}

# (adresse fichier, octets d'origine, octets neufs)
PATCH_DATE = [
    (0x03F0D, '9f0661', '9f0461'),   # incw 1,(XSP+6) -> (XSP+4) : le jour s'écrit en premier
    (0x03F10, '9f0620', '9f0420'),
    (0x03F38, '9f0620', '9f0420'),
    (0x03F53, '9f0461', '9f0661'),   # puis le mois
    (0x03F56, '9f0420', '9f0620'),
    (0x03F74, '9f0420', '9f0620'),
    (0x03F1B, '660f', '0000'),       # dizaine du 1er nombre toujours écrite (« 04 »)
    (0x03F61, '660b', '0000'),       # dizaine du 2e nombre toujours écrite
    (0x03F4C, 'd8ce0d00', 'd8ce1d00'),  # 月 -> « / »
    (0x03F88, 'd8ce0c00', 'd8ce0000'),  # 日 -> case vide
    # Phrases du rendez-vous : voir date_fr.py (routine en puce 2, chiffres étroits).
    # Date des journaux de sauvegarde (« Journal 1  11/ 4 ») : vu « 4/ 11 » à l'écran le 20/11.
    (0x128FC, '1e', '1c'),           # 0x2128FB pushw (XSP+30 -> 28) : le jour (x=72)
    (0x1291D, '24', '26'),           # 0x21291C pushw (XSP+36 -> 38) : le mois (x=108)
]


def tuile(lignes):
    b = bytearray(2)                 # ligne 0 vide
    for l in lignes:
        w = 0
        for x, c in enumerate(l[:8]):
            w |= ('.123'.index(c)) << (14 - 2 * x)
        b += bytes([w & 255, w >> 8])
    return bytes(b)


def applique(out, rom):
    off = struct.unpack_from('<I', rom, 0x20004 + 8 * 39)[0]
    base = 0x20000 + off + 2
    for k, lettre in JOURS.items():
        out[base + 16 * k:base + 16 * k + 16] = tuile(LETTRES[lettre])
    out[base + 16 * 31:base + 16 * 31 + 16] = tuile(YEN)
    # « ・ » (tuile 28, inutilisée) -> « : » pour les aides du planning (petite police, encre 3)
    out[base + 16 * 28:base + 16 * 28 + 16] = tuile(["........", ".3......", "........", "........", ".3......", "........", "........"])
    for a, avant, apres in PATCH_DATE:
        n = len(avant) // 2
        if bytes(out[a:a + n]) != bytes.fromhex(avant):
            raise SystemExit('ROM inattendue (date, 0x%06X)' % (0x200000 + a))
        out[a:a + n] = bytes.fromhex(apres)
