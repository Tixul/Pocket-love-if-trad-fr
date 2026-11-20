"""Extrait le texte japonais de VOTRE ROM -> out/ja_script.txt, out/ja_interface.txt, out/ja_dico.txt
(référence pour traduire ; ce texte n'est pas distribué).

    python tools/extract.py "Pocket Love - if (Japan).ngc"

Archive en 0x20000 : u32 nb, puis nb x (u32 offset rel. 0x20000, u32 taille).
Entrée 10 = script (10 200 messages), 11 = interface (582), 9 = dictionnaire {E00}-{E0A}.
Chaque entrée texte : table d'offsets u32 (nb = 1er offset / 4), puis texte en codes
12 bits empaquetés (3 octets = 2 codes, gros-boutiste par quartets).
"""
import os, struct, sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
T = {}
for l in open(ICI / 'table.tbl', encoding='utf-8'):
    if l.startswith('#') or '=' not in l:
        continue
    k, v = l.rstrip('\n').split('=', 1)
    T[int(k, 16)] = v


def codes(r, a, b):
    out = []
    while a + 3 <= b:
        x = r[a:a + 3]; a += 3
        out += [(x[0] << 4) | (x[1] >> 4), ((x[1] & 15) << 8) | x[2]]
    return out


def main():
    r = open(sys.argv[1], 'rb').read()
    n = struct.unpack_from('<I', r, 0x20000)[0]
    ents = [struct.unpack_from('<II', r, 0x20004 + 8 * i) for i in range(n)]
    for e, nom in ((10, 'ja_script.txt'), (11, 'ja_interface.txt'), (9, 'ja_dico.txt')):
        base, size = 0x20000 + ents[e][0], ents[e][1]
        m = struct.unpack_from('<I', r, base)[0] // 4
        offs = [struct.unpack_from('<I', r, base + 4 * k)[0] for k in range(m)] + [size]
        lignes = []
        for k in range(m):
            cs = codes(r, base + offs[k], base + offs[k + 1])
            lignes.append('%05d %s' % (k, ''.join(T.get(c, '{%03X}' % c) for c in cs)))
        (ICI.parent / 'out').mkdir(exist_ok=True)
        dst = ICI.parent / 'out' / nom
        tmp = dst.with_suffix('.tmp')
        tmp.write_text('\n'.join(lignes) + '\n', encoding='utf-8')
        os.replace(tmp, dst)
        print(dst, m, 'messages')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()
