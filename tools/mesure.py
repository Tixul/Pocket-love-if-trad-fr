"""Largeur en pixels de chaque ligne d'un texte : python -I -B tools/mesure.py "texte|ligne 2" """
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__('os').path.dirname(__file__))
import build  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')
for ligne in sys.argv[1].split('|'):
    cs = build.encode(ligne)
    print('%3d px  %s' % (sum(build.largeur(c, {3: 9}) for c in cs), ligne))
