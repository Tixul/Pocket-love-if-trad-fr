"""Police française à chasse variable, tirée du bitmap 12 px de MS Gothic (la police du jeu
en est déjà une copie exacte pour les kanji).

Les glyphes neufs vont dans les cases LIBRES de la police (codes 0x9BC..0xBFE, case 3071
occupée) ; chaque glyphe est collé à gauche, sa largeur d'avance = dernière colonne + 2.
"""
from PIL import Image, ImageDraw, ImageFont

POLICE_TTF = r'C:\Windows\Fonts\msgothic.ttc'
PREMIER_CODE = 0x9BC
DERNIER_CODE = 0xBFE
LARGEUR_JP = 12          # tous les glyphes d'origine
LARGEUR_ESPACE = 4
DECALAGE_CLAVIER = 0x80

CARS = ("abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "éèêëàâäîïôöûùüçœæ"
        "ÉÈÊËÀÂÎÏÔÛÙÇŒ"
        ".,;:!?'\"-()/%&+=*#«»")

# Glyphes liés pour les suffixes de nom insérés par le jeu (table 0x21A820, 3 codes par suffixe) :
# « -kun » = « -k » + « un », « -san » = « -s » + « an ».
LIGATURES = {'': '-k', '': 'un', '': '-s', '': 'an'}

# Ponctuation laissée aux glyphes d'origine du jeu (plus lisibles) mais à chasse réduite
REMPLACE = {'…': '…', '♥': '♥', '♪': '♪', '~': '〜'}


def _rendu(ch, font):
    im = Image.new('L', (16, 14), 0)
    ImageDraw.Draw(im).text((0, -1), ch, font=font, fill=255)
    px = im.load()
    pts = [(x, y) for y in range(12) for x in range(16) if px[x, y] > 127]
    return pts


def glyphes():
    """-> dict car -> (code, largeur, 18 octets du glyphe 12x12 1bpp)."""
    font = ImageFont.truetype(POLICE_TTF, 12)
    out = {}
    code = PREMIER_CODE
    out[' '] = (code, LARGEUR_ESPACE, bytes(18))
    code += 1
    for fin in (1, 2, 3):            # espaces fins pour caler au pixel ({>N})
        out[chr(fin)] = (code, fin, bytes(18))
        code += 1
    # blancs larges (24 / 48 / 96 px) : {>N} coûte 1 code au lieu de 8 pour 96 px (limite de 128 codes).
    # ⚠ ils n'effacent que 12 px : les lignes d'espaces japonais qui EFFACENT une fenêtre restent en « 　 ».
    for k, larg in ((4, 24), (5, 48), (6, 96)):
        out[chr(k)] = (code, larg, bytes(18))
        code += 1
    for ch in CARS + ''.join(LIGATURES):
        pts = _rendu(LIGATURES.get(ch, ch), font)
        if not pts:
            raise ValueError('glyphe vide : %r' % ch)
        x0 = min(x for x, _ in pts)
        x1 = max(x for x, _ in pts)
        bits = 0
        for x, y in pts:
            xx = x - x0
            if xx < 12:
                bits |= 1 << (143 - (y * 12 + xx))
        larg = (x1 - x0) + 2
        out[ch] = (code, larg, bits.to_bytes(18, 'big'))
        code += 1
    if code > PREMIER_CODE + DECALAGE_CLAVIER:
        raise ValueError('police : le bloc étroit déborde sur le bloc clavier')
    return out


def glyphes_clavier():
    """Codes « clavier » : même lettre, CENTRÉE dans 12 px, avance 12 (la grille du clavier de
    saisie du nom reste alignée). Code = code étroit + DECALAGE_CLAVIER ; le crochet 0x211885
    les reconvertit en codes étroits quand un nom est inséré dans un dialogue."""
    out = {}
    for ch, (code, larg, bits) in glyphes().items():
        if ch in ('', '', ''):
            continue
        v = int.from_bytes(bits, 'big')
        dx = max(0, (12 - larg + 1) // 2)
        w = 0
        for y in range(12):
            ligne = (v >> (143 - 12 * y - 11)) & 0xFFF
            w |= ((ligne >> dx) & 0xFFF) << (132 - 12 * y)
        k = code + DECALAGE_CLAVIER
        if k > DERNIER_CODE:
            raise ValueError('police pleine')
        out[ch] = (k, 12, w.to_bytes(18, 'big'))
    return out
