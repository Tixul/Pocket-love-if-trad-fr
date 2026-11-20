"""Date des phrases du rendez-vous : « Rendez-vous le 18/4 » / « au matin ! ».

Le jeu japonais écrit, sur la 2e ligne : mois (sub_211BE0, chiffres pleine chasse 12 px alignés à
droite), 月 (#418), jour, 日 (#419), puis le moment (#415/#416 ou #428/#429) en x=72. En français
cela donnait « 1 8/   4    au matin ». On remplace l'appel du 1er nombre par la routine DATE_FR
(CPU 0x800200, source tools/asm/date_fr.asm, assemblée avec AS) qui écrit « jour/mois » en chiffres
étroits d'un seul tenant, en fin de 1re ligne, juste après « Rendez-vous le » ; « / », mois et case
vide sont neutralisés (appels remplacés par des nop, la pile reste nettoyée par l'appelant) et le
moment passe en début de 2e ligne (x=0).
"""
X_DATE = 81            # largeur de « Rendez-vous le » (77 px) + espace (4)
ADR = 0x200200         # fichier (CPU 0x800200)
CHIFFRE0, BARRE = 0x9F7, 0xA2A

# tools/asm/date_fr.asm assemblé (asl -cpu 96C141 ; p2bin)
CODE = bytes.fromhex(
    '3e3a393bbff037b7329f2a201d4b0280312a0ab242ba0143ea629f28201d4b02'
    '8031ff0fb242ba01439f2420c88bcaa829c8a8289f2a2028bf0631391d3b1a21'
    'bf0a37bf10375b595a5e0edba8e812d80a0a003849d988db61d8d86ef049d9c8'
    'f709b242ba0143ea62db69dbd86eee0e')


def _pousse_date(jour, mois, y, drapeau):
    return bytes([0x9F, jour, 0x04, 0x9F, mois, 0x04, 0x0B, X_DATE, 0x00, 0x0B, y, drapeau]) \
        + bytes.fromhex('1d000280')


# (adresse fichier, octets d'origine, octets neufs)
PATCHS = [
    # phrase après le choix (0x20BD9B) : pile XSP0+18 = jour, +20 = mois
    (0x0BD9B, '0b00000b0c000b0c009f1a041de01b21', _pousse_date(0x12, 0x16, 0x00, 0)),
    (0x0BDBA, '1e2dfa', '000000'),             # « / » (#418)
    (0x0BDC9, '1de01b21', '00000000'),         # mois
    (0x0BDD9, '1e0efa', '000000'),             # case vide (#419)
    (0x0BDE2, '0b4800', '0b0000'),             # moment : x 72 -> 0 (ligne 2)
    # récapitulatif (0x20C173) : pile XSP0+4 = jour, +6 = mois ; ligne y=0x24, drapeau 4
    (0x0C173, '0b00000b30000b0c009f0c041de01b21', _pousse_date(0x04, 0x08, 0x24, 4)),
    (0x0C18F, '1da61b21', '00000000'),
    (0x0C19F, '1de01b21', '00000000'),
    (0x0C1AF, '1da61b21', '00000000'),
    (0x0C1BC, '0b4800', '0b0000'),             # moment : x 72 -> 0 (ligne y=0x30)
    # liste « quel jour ? » (0x20BC69) : mois (x=24), jour (x=60), « / » (#413) ; pile XSP0+24 = jour,
    # +26 = mois ; y de la ligne = IZ*12 + 0x24 -> un seul appel DATE_FR, x = 24.
    (0x0BC69, '0b0000de88d8080c00d8c82400280b18009f20041de01b21'
              '0b0000de88d8080c00d8c82400280b3c009f26041de01b21',
     bytes.fromhex('de88d8080c00d8c82400' '9f1804' '9f1c04' '0b1800' '28' '1d000280') + bytes(24)),
    (0x0BC99, 'bf1a37', 'bf1237'),             # nettoyage : 16 -> 8 octets poussés
    (0x0BCB0, '1da61b21', '00000000'),         # « / » (#413)
]


# Générique (sub_21439B) : centrage à la largeur réelle. tools/asm/centre_fr.asm (CPU 0x800280)
ADR_CENTRE = 0x200280
CODE_CENTRE = bytes.fromhex(
    '393aee89daa88120890121d8cfff0f6617c8cf0f660ee812e8c8001080008021'
    'd812d882e96268deda88d8ef015a590e')
PATCHS.append((0x143C6, 'ee89d8a8813f0f6e0689013fff660b813f0f6602d861e96268ead8080c00d8ef01',
               bytes.fromhex('1d800280' '681b') + bytes(27)))   # call 0x800280 ; jr 0x2143E7


def applique(out, fr):
    if out[ADR_CENTRE:ADR_CENTRE + len(CODE_CENTRE)] != b'\xff' * len(CODE_CENTRE):
        raise SystemExit('date_fr : place 0x800280 occupée')
    out[ADR_CENTRE:ADR_CENTRE + len(CODE_CENTRE)] = CODE_CENTRE
    if fr['0'] != CHIFFRE0 or fr['/'] != BARRE:
        raise SystemExit('date_fr : codes police changés, réassembler tools/asm/date_fr.asm')
    if out[ADR:ADR + len(CODE)] != b'\xff' * len(CODE):
        raise SystemExit('date_fr : place 0x800200 occupée')
    out[ADR:ADR + len(CODE)] = CODE
    for a, avant, apres in PATCHS:
        avant = bytes.fromhex(avant)
        apres = bytes.fromhex(apres) if isinstance(apres, str) else apres
        if bytes(out[a:a + len(avant)]) != avant or len(apres) != len(avant):
            raise SystemExit('ROM inattendue (date_fr, 0x%06X)' % (0x200000 + a))
        out[a:a + len(apres)] = apres
