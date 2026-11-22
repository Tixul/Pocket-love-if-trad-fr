"""Construit la ROM française de Pocket Love if.

    python tools/build.py --rom JP.ngc [--lang fr] [--verif] [--ips] [--identite]

- --rom : la ROM japonaise d'origine (2 Mio, CRC32 C2EE1EE5), toute autre est refusée.
- --lang : dossier lang/<code>/ (défaut fr). Sortie : out/<code>.ngc, et out/<code>.ips avec --ips.

- ROM de sortie : 4 Mio. Puce 1 = ROM d'origine (police française ajoutée dans les cases
  libres, crochet de chasse variable en 0x211A28). Puce 2 (fichier 0x200000 = CPU 0x800000) :
  code du crochet, table des largeurs, entrées texte 9/10/11 reconstruites.
- ⛔ 0x1C0000-0x1FFFFF de la puce 1 = FLASH DES SAUVEGARDES (sub_21517F), jamais y écrire.
- Fichiers de traduction lang/<code>/*.txt :
      @NNNNN<TAB>texte   message du script (entrée 10)
      #NNNN<TAB>texte    message d'interface (entrée 11)
      %NN<TAB>texte      mot du dictionnaire {E00}-{E0A} (entrée 9)
  ';' en début de ligne = commentaire. Balises : {n} ou | (ligne), {attente}, {page}, {fin},
  {E0x} (mot du dictionnaire), {F0x} (surnom du joueur), {XYZ} = code hexa brut.
- --identite : reconstruit sans traduction et compare aux entrées d'origine (test d'aller-retour).
"""
import os
import re
import struct
import zlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
PROJET = ICI.parent
sys.path.insert(0, str(ICI))
import police_fr  # noqa: E402

CRC_JP = 0xC2EE1EE5
LANGUE = 'fr'

ARCHIVE = 0x20000
BASE_CPU_ARCHIVE = 0x220000
POLICE = 0x2030C
PUCE2 = 0x200000            # fichier
PUCE2_CPU = 0x800000
CROCHET = 0x11A28           # fichier (CPU 0x211A28) : add (0x428A),0x0C  -> call 0x800000 ; nop ; nop
CROCHET_ORIG = bytes.fromhex('c28a4200380c')
CODE_VWF = bytes.fromhex(
    '39'              # push xbc
    'e17e4220'        # ld xwa,(0x427E)      pointeur du caractère courant (hi, lo)
    '8022'            # ld b,(xwa)
    '880123'          # ld c,(xwa+1)
    'e912'            # extz xbc            -> code 12 bits
    '4000108000'      # ld xwa,0x801000     table des largeurs
    'e980'            # add xwa,xbc
    '8021'            # ld a,(xwa)
    'c18a4281'        # add a,(0x428A)
    'f18a4241'        # ld (0x428A),a
    '59'              # pop xbc
    '0e')             # ret
# Crochet n°2 (CPU 0x211885, fin de l'insertion d'un nom {F0x} dans le tampon 0x4390) :
# reconvertit les codes « clavier » (0xA3C-0xABB, avance 12) en lettres étroites (code - 0x80).
CROCHET_NOM = 0x11885
CROCHET_NOM_ORIG = bytes.fromhex('f28642000001')   # ld (0x4286),1
CODE_NOM = bytes.fromhex(
    '38393a'          # push xwa / xbc / xde
    'c9a9'            # ld a,1
    'f1864241'        # ld (0x4286),a        (instruction remplacée)
    '4290430000'      # ld xde,0x4390
    '8222'            # boucle: ld b,(xde)
    '8a0123'          # ld c,(xde+1)
    'd9cfff0f'        # cp bc,0x0FFF
    '6619'            # jr z,fin
    'd9cf3c0a'        # cp bc,0xA3C
    '670f'            # jr c,suite
    'd9cfbc0a'        # cp bc,0xABC
    '6f09'            # jr nc,suite
    'd9ca8000'        # sub bc,0x80
    'b242'            # ld (xde),b
    'ba0143'          # ld (xde+1),c
    'ea62'            # suite: inc 2,xde
    '68dc'            # jr boucle
    '5a59580e')       # fin: pop xde / xbc / xwa ; ret
ADR_CODE_NOM = 0x40         # relatif à la puce 2 (CPU 0x800040)
TABLE_LARG = 0x1000         # relatif à la puce 2
DONNEES = 0x2000            # relatif à la puce 2 : entrées reconstruites

TAMPON_CODES = 128          # tampon RAM 0x4290..0x438F
LARGEUR_BOITE = 144         # mesuré à l'écran : au-delà, le jeu renvoie à la ligne
LARGEUR_LIGNE4 = 136        # 4e ligne : l'icône d'attente ♥ commence vers 137 px
LIGNES_PAGE = 4
LARGEUR_SURNOM = 42         # {F02}-{F08} surnom : 6 lettres saisies, ~7 px
LARGEUR_NOM = 36            # {F00} nom, {F01} prénom : 5 lettres

CTRL = {'n': 0xFFE, 'attente': 0xFFC, 'page': 0xFFD, 'fin': 0xFFF}


def charge_table():
    t = {}
    for ligne in open(ICI / 'table.tbl', encoding='utf-8'):
        if ligne.startswith('#') or '=' not in ligne:
            continue
        k, v = ligne.rstrip('\n').split('=', 1)
        t[int(k, 16)] = v
    return t


TABLE = charge_table()
INV_JP = {}
for _c, _v in TABLE.items():
    if len(_v) == 1:
        INV_JP.setdefault(_v, _c)
GLY = police_fr.glyphes()
GLY_K = police_fr.glyphes_clavier()
CLAVIER = {ch: g[0] for ch, g in GLY_K.items()}
FR = {ch: g[0] for ch, g in GLY.items()}
LARG = {g[0]: g[1] for g in GLY.values()}
SPECIAUX = {'~': 0x0A6, '♥': 0x0EE, '♪': 0x0F4, '「': 0x0E8, '」': 0x0E9}


def codes_de(r, a, b):
    out = []
    while a + 3 <= b:
        x = r[a:a + 3]
        a += 3
        out += [(x[0] << 4) | (x[1] >> 4), ((x[1] & 15) << 8) | x[2]]
    return out


def lit_entree(r, i):
    off, taille = struct.unpack_from('<II', r, ARCHIVE + 4 + 8 * i)
    base = ARCHIVE + off
    n = struct.unpack_from('<I', r, base)[0] // 4
    offs = [struct.unpack_from('<I', r, base + 4 * k)[0] for k in range(n)] + [taille]
    return base, taille, [r[base + offs[k]:base + offs[k + 1]] for k in range(n)]


def encode(texte, jp=False, dico=False):
    """texte (balises) -> liste de codes 12 bits. jp=True : texte issu de l'extraction."""
    if not jp:
        texte = texte.replace('|', '{n}').replace('…', '...')
        if not dico:      # le mot {E03} lui-même ne doit pas se citer (boucle infinie)
            texte = texte.replace('...', '{E03}')
    out = []
    x = 0
    i = 0
    clavier = False
    japonais = False
    while i < len(texte):
        ch = texte[i]
        if ch == '{':
            j = texte.index('}', i)
            tag = texte[i + 1:j]
            i = j + 1
            if tag == 'clavier':      # lettres du clavier de saisie : codes « clavier », espace = case vide
                clavier = True
                continue
            if tag in ('ja', 'fr'):   # {ja}...{fr} : texte recopié avec la table japonaise d'origine
                japonais = tag == 'ja'
                continue
            if tag.startswith('>'):
                # caler la suite à la colonne N pixels : espaces de 12 puis de 4
                but = int(tag[1:])
                reste = but - x
                if reste < 0:
                    raise ValueError('{%s} impossible depuis x=%d' % (tag, x))
                for k, larg in ((6, 96), (5, 48), (4, 24)):   # blancs larges d'abord
                    out += [FR[chr(k)]] * (reste // larg)
                    reste %= larg
                out += [0x000] * (reste // 12) + [FR[' ']] * ((reste % 12) // 4)
                if reste % 4:
                    out.append(FR[chr(reste % 4)])
                x = but
                continue
            c = CTRL[tag] if tag in CTRL else int(tag, 16)
            out.append(c)
            if c in (0xFFE, 0xFFD):
                x = 0
            elif c < 0xE00:
                x += LARG.get(c, 12)
            elif 0xF09 <= c <= 0xF0B:
                pass              # couleur
            elif c == 0xFFB:
                x += 12           # tabulation : le jeu avance de 12 px (0x2118C2)
            else:
                x = -10 ** 6      # mot ou surnom : largeur inconnue ici
            continue
        if clavier:
            out.append(0x000 if ch == ' ' else CLAVIER[ch])
        elif jp or japonais:
            out.append(INV_JP[ch])
        elif ch in FR:
            out.append(FR[ch])
        elif ch in SPECIAUX:
            out.append(SPECIAUX[ch])
        elif ch in INV_JP:
            out.append(INV_JP[ch])
        else:
            raise ValueError('caractère sans glyphe : %r' % ch)
        x += LARG.get(out[-1], 12)
        i += 1
    return out


def empaquette(codes):
    if len(codes) % 2:
        codes = codes + [0]
    b = bytearray()
    for k in range(0, len(codes), 2):
        a, c = codes[k], codes[k + 1]
        b += bytes([a >> 4, ((a & 15) << 4) | (c >> 8), c & 255])
    return bytes(b)


def largeur(c, dico_larg):
    if c in (0xF00, 0xF01):
        return LARGEUR_NOM
    if 0xF02 <= c <= 0xF08:
        return LARGEUR_SURNOM
    if 0xE00 <= c <= 0xEFF:
        return dico_larg.get(c & 0xFF, 0)
    if c == 0xFFB:
        return 12                  # tabulation (0x2118C2 : add (0x428A),12)
    if c >= 0xF00:
        return 0
    return LARG.get(c, 12)


def controle(nom, codes, dico_larg, interface=False):
    err = []
    lignes_max = 99 if interface else LIGNES_PAGE
    larg_max = LARGEUR_BOITE      # interface aussi : au-delà de 144 px le moteur renvoie à la ligne
    if len(codes) > TAMPON_CODES:
        err.append('%d codes > %d (tampon RAM)' % (len(codes), TAMPON_CODES))
    if not codes or codes[-1] != 0xFFF:
        err.append('ne finit pas par {fin}')
    x, lignes = 0, 1
    for c in codes:
        if c == 0xFFE:
            x, lignes = 0, lignes + 1
        elif c == 0xFFD:
            x, lignes = 0, 1
        else:
            x += largeur(c, dico_larg)
            if x > (LARGEUR_LIGNE4 if lignes == 4 and not interface else larg_max):
                err.append('ligne %d trop large (%d px)' % (lignes, x))
                x = -10 ** 6
        if lignes > lignes_max:
            err.append('%d lignes dans la boîte' % lignes)
            lignes = -10 ** 6
    return ['%s : %s' % (nom, e) for e in err]


ERREURS_LECTURE = []


def lit_trad():
    """Lit lang/<code>/*.txt. Une ligne fautive devient une erreur de SON fichier (plusieurs
    traducteurs vérifient en parallèle : le fichier d'un autre ne doit bloquer personne)."""
    t = {9: {}, 10: {}, 11: {}}
    pref = {'@': 10, '#': 11, '%': 9}
    for f in sorted((PROJET / 'lang' / LANGUE).glob('*.txt')):
        try:
            lignes = open(f, encoding='utf-8').read().split('\n')
        except (OSError, UnicodeDecodeError) as ex:
            ERREURS_LECTURE.append('%s:0 : illisible (%s)' % (f.name, ex))
            continue
        for no, ligne in enumerate(lignes, 1):
            ligne = ligne.rstrip('\r')
            if not ligne.strip() or ligne.startswith(';'):
                continue
            cle, _, texte = ligne.partition('\t')
            if ligne[0] not in pref or not texte or not cle[1:].isdigit():
                ERREURS_LECTURE.append('%s:%d : ligne illisible' % (f.name, no))
                continue
            e, k = pref[ligne[0]], int(cle[1:])
            if k in t[e]:
                ERREURS_LECTURE.append('%s:%d : %s déjà traduit dans %s' % (f.name, no, cle, t[e][k][1]))
                continue
            t[e][k] = (texte, '%s:%d' % (f.name, no))
    return t


def construit_entree(r, i, trad, dico_larg, erreurs):
    _, _, msgs = lit_entree(r, i)
    corps = []
    # message japonais identique à un message traduit -> même traduction (9 707 textes pour 10 200)
    double = {}
    for k in sorted(trad):
        double.setdefault(msgs[k], k)
    for k, brut in enumerate(msgs):
        if k not in trad and brut in double:
            k = double[brut]
        if k in trad:
            texte, ou = trad[k]
            try:
                codes = encode(texte, dico=(i == 9))
            except (ValueError, KeyError) as ex:
                erreurs.append('%s : %s' % (ou, ex))
                codes = [0xFFF]
            erreurs += controle(ou, codes, dico_larg, interface=(i == 11))
            corps.append(empaquette(codes))
        else:
            corps.append(brut)
    n = len(msgs)
    table, pos = [], 4 * n
    for b in corps:
        table.append(pos)
        pos += len(b)
    return b''.join(struct.pack('<I', o) for o in table) + b''.join(corps)


def main():
    args = sys.argv[1:]
    connues = {'--rom', '--lang', '--identite', '--verif', '--fichier', '--ips'}
    for k, a in enumerate(args):
        if a.startswith('-') and a not in connues:
            raise SystemExit(__doc__)
    global LANGUE
    if '--rom' not in args:
        raise SystemExit(__doc__)
    rom = args[args.index('--rom') + 1]
    if '--lang' in args:
        LANGUE = args[args.index('--lang') + 1]
    r = open(rom, 'rb').read()
    if len(r) != 0x200000 or zlib.crc32(r) != CRC_JP:
        raise SystemExit("ROM inattendue : il faut la ROM japonaise d'origine (2 Mio, CRC32 %08X)" % CRC_JP)
    if r[CROCHET:CROCHET + 6] != CROCHET_ORIG:
        raise SystemExit('ROM inattendue (crochet 0x211A28)')

    if '--identite' in args:
        bon = True
        for i in (9, 10, 11):
            base, taille, _ = lit_entree(r, i)
            neuf = construit_entree(r, i, {}, {}, [])
            # aller-retour texte : décoder puis réencoder chaque message
            _, _, msgs = lit_entree(r, i)
            for k, brut in enumerate(msgs):
                cs = codes_de(brut, 0, len(brut))
                txt = ''.join(TABLE.get(c, '{%03X}' % c) for c in cs)
                if empaquette(encode(txt, jp=True)) != brut:
                    print('entrée %d message %d : aller-retour différent' % (i, k))
                    bon = False
                    break
            print('entrée %d : %s' % (i, 'identique' if neuf == r[base:base + taille] else 'DIFFÉRENTE'))
            bon &= neuf == r[base:base + taille]
        raise SystemExit(0 if bon else 1)

    trad = lit_trad()
    erreurs = []
    # largeur des mots du dictionnaire (traduits ou non)
    _, _, dico = lit_entree(r, 9)
    dico_larg = {}
    for k, brut in enumerate(dico):
        if k in trad[9]:
            cs = encode(trad[9][k][0], dico=True)
        else:
            cs = codes_de(brut, 0, len(brut))
        dico_larg[k] = sum(LARG.get(c, 12) for c in cs if c < 0xE00)

    out = bytearray(r) + bytearray(b'\xff' * 0x200000)
    # police
    for code, larg, bits in GLY.values():
        a = POLICE + code * 18
        if out[a:a + 18] != bytes(18):
            raise SystemExit('case de police %03X occupée' % code)
        out[a:a + 18] = bits
    # crochet + table des largeurs
    out[CROCHET:CROCHET + 6] = bytes.fromhex('1d000080') + b'\x00\x00'
    if out[CROCHET_NOM:CROCHET_NOM + 6] != CROCHET_NOM_ORIG:
        raise SystemExit('ROM inattendue (crochet 0x211885)')
    out[CROCHET_NOM:CROCHET_NOM + 6] = bytes.fromhex('1d400080') + b'\x00\x00'
    out[PUCE2 + ADR_CODE_NOM:PUCE2 + ADR_CODE_NOM + len(CODE_NOM)] = CODE_NOM
    # suffixes ajoutés aux noms {F0x} (table 0x21A820, 3 codes hi/lo) : 君 -> -kun, さん -> -san
    if out[0x1A826:0x1A832] != bytes.fromhex('02a00fff0fff' '001500510fff'):
        raise SystemExit('ROM inattendue (suffixes 0x21A820)')
    for a, (c1, c2) in ((0x1A826, ('', '')), (0x1A82C, ('', ''))):
        out[a:a + 6] = b''.join(struct.pack('>H', c) for c in (FR[c1], FR[c2], 0xFFF))
    for code, larg, bits in GLY_K.values():
        a = POLICE + code * 18
        if out[a:a + 18] != bytes(18):
            raise SystemExit('case de police %03X occupée' % code)
        out[a:a + 18] = bits
    out[PUCE2:PUCE2 + len(CODE_VWF)] = CODE_VWF
    lt = bytearray([12] * 0x1000)
    for code, larg in LARG.items():
        lt[code] = larg
    out[PUCE2 + TABLE_LARG:PUCE2 + TABLE_LARG + 0x1000] = lt
    # entrées texte
    pos = PUCE2 + DONNEES
    for i in (9, 10, 11):
        donnees = construit_entree(r, i, trad[i], dico_larg, erreurs)
        cpu = PUCE2_CPU + (pos - PUCE2)
        struct.pack_into('<II', out, ARCHIVE + 4 + 8 * i, cpu - BASE_CPU_ARCHIVE, len(donnees))
        out[pos:pos + len(donnees)] = donnees
        pos += (len(donnees) + 15) & ~15
    # lettrages de l'écran titre (sprites)
    import titre_fr
    # bandeau : date « 10/04 (S) », jours de la semaine en une lettre
    import hud_fr
    hud_fr.applique(out, r)
    # phrases du rendez-vous : « Rendez-vous le 18/4 » (routine 0x800200, chiffres étroits)
    import date_fr
    date_fr.applique(out, FR)
    # écran de planning : libellés et aides (petite police de l'entrée 55)
    import planning_fr
    pos = planning_fr.applique(out, r, pos, PUCE2_CPU)
    # onglets du clavier de saisie du nom (entrée 50)
    import clavier_fr
    clavier_fr.applique(out, r)
    # écran Relations : plaques de nom (entrée 67) et libellés LOVE / ÉLAN / LIEN / RDV (entrée 69)
    import relations_fr
    relations_fr.applique(out, r)
    # libellés des stats (entrée 52)
    import stats_fr
    donnees = stats_fr.entree(r, planning_fr.cases_libres(r), out)
    struct.pack_into('<II', out, ARCHIVE + 4 + 8 * 52, PUCE2_CPU + (pos - PUCE2) - BASE_CPU_ARCHIVE, len(donnees))
    out[pos:pos + len(donnees)] = donnees
    pos += (len(donnees) + 15) & ~15
    # logo latin (entrée 87, plan de fond) + cœurs (sprites 89/93, descripteurs 0 et 1)
    import logo
    donnees, coeurs, nb_tuiles = logo.entree_logo(r)
    if nb_tuiles > 128:
        raise SystemExit('logo : %d tuiles, le fond fleuri commence en 128' % nb_tuiles)
    cpu = PUCE2_CPU + (pos - PUCE2)
    struct.pack_into('<II', out, ARCHIVE + 4 + 8 * 87, cpu - BASE_CPU_ARCHIVE, len(donnees))
    out[pos:pos + len(donnees)] = donnees
    pos += (len(donnees) + 15) & ~15
    for k, (cx, cy) in enumerate(coeurs):
        a = titre_fr.DESCRIPTEURS + 10 * k
        struct.pack_into('<HH', out, a + 6, cx, cy)
    lettrages = titre_fr.entrees(r)
    for a, desc in titre_fr.descripteurs(r, lettrages):
        out[a:a + 10] = desc
    # surbrillance du menu titre : la boucle 0x20E044 recolorait 16 sprites fixes par option
    # (cp IY,0x10) -> crochet qui compare IY au vrai nombre de sprites de l'option DE.
    if out[0xE067:0xE06D] != bytes.fromhex('ddcf100067d7'):
        raise SystemExit('ROM inattendue (menu titre 0x20E067)')
    out[0xE067:0xE06B] = bytes.fromhex('1da00080')        # call 0x8000A0 ; le jr C suit
    # clignotement : l'option est cachée en posant son 1er sprite en x=160, y=0 ; un lettrage
    # de plus de 96 px repasse alors par x=0 (le « e » fantôme). On cache en y=160, x=0.
    if out[0xDEA8:0xDEAE] != bytes.fromhex('0b00000ba000'):
        raise SystemExit('ROM inattendue (menu titre 0x20DEA8)')
    out[0xDEA8:0xDEAE] = bytes.fromhex('0ba0000b0000')
    nb = [lettrages[e][0] for _, e in titre_fr.MENU]   # nombre de sprites de chaque option
    out[PUCE2 + 0x90:PUCE2 + 0x90 + len(nb)] = bytes(nb)
    out[PUCE2 + 0xA0:PUCE2 + 0xB2] = bytes.fromhex(
        '3a'              # push xde
        'ea12'            # extz xde
        '4090008000'      # ld xwa,0x800090      table des nombres de sprites
        'ea80'            # add xwa,xde
        '8021'            # ld a,(xwa)
        '5a'              # pop xde
        'd812'            # extz wa
        'd8f5'            # cp iy,wa             C si IY < nombre
        '0e')             # ret
    for i, donnees in lettrages.items():
        cpu = PUCE2_CPU + (pos - PUCE2)
        struct.pack_into('<II', out, ARCHIVE + 4 + 8 * i, cpu - BASE_CPU_ARCHIVE, len(donnees))
        out[pos:pos + len(donnees)] = donnees
        pos += (len(donnees) + 15) & ~15
    if pos > len(out):
        raise SystemExit('puce 2 pleine')

    nb = sum(len(v) for v in trad.values())
    erreurs = ERREURS_LECTURE + erreurs
    if '--fichier' in args:
        nom = Path(args[args.index('--fichier') + 1]).name + ':'
        erreurs = [e for e in erreurs if e.startswith(nom)]
    for e in erreurs:
        print('ERREUR', e)
    print('%d messages traduits, %d erreur(s), puce 2 utilisée : %d Kio'
          % (nb, len(erreurs), (pos - PUCE2) // 1024))
    if erreurs or '--verif' in args:
        raise SystemExit(1 if erreurs else 0)
    sortie = PROJET / 'out' / (LANGUE + '.ngc')
    sortie.parent.mkdir(exist_ok=True)
    tmp = sortie.with_suffix('.tmp')
    tmp.write_bytes(out)
    os.replace(tmp, sortie)
    print(sortie)
    if '--ips' in args:
        import ips
        p = ips.fabrique(r, bytes(out))
        dst = sortie.with_suffix('.ips')
        tmp = dst.with_suffix('.tmp')
        tmp.write_bytes(p)
        os.replace(tmp, dst)
        print(dst, len(p), 'octets')


if __name__ == '__main__':
    main()
