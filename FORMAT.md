# Pocket Love ~if~ — notes techniques (ROM, texte, interface)

Tout ce qui suit a été mesuré sur la ROM japonaise d'origine (2 Mio, CRC32 `C2EE1EE5`).
Adresses CPU : la cartouche commence en 0x200000 (fichier 0 = CPU 0x200000) ; la 2e puce de
la ROM française (fichier 0x200000) est vue en CPU 0x800000.

## Chaîne de construction
`tools/build.py` : ROM japonaise → police latine ajoutée dans les cases libres de la police →
crochets de code (chasse variable, noms, menu titre, dates, générique) → textes français
reconstruits en 2e puce → graphismes (logo, lettrages du titre, planning, stats, bandeau, clavier)
→ ROM française de **4 Mio** → patch IPS **depuis la ROM japonaise**.
`--identite` : sans traduction, les entrées texte reconstruites sont identiques à l'octet près.

⛔ Fichier 0x1C0000-0x1FFFFF (rempli de FF) = **flash des sauvegardes** (routine 0x21517F) :
ce n'est pas de la place libre, rien n'y est écrit. Tout le neuf va dans la 2e puce.

## L'archive (fichier 0x20000)
`u32 nombre` (97), puis pour chaque entrée `u32 offset (relatif à 0x20000), u32 taille`.
Adresse CPU d'une entrée = 0x220000 + offset ; les offsets sont sur 32 bits, une entrée peut donc
être déplacée n'importe où (c'est ainsi que les textes et graphismes français vont en 2e puce).

| entrée | contenu |
|---|---|
| 0 | police 12×12, 1 bpp, 18 octets par glyphe (fichier 0x2030C), copie exacte du bitmap MS Gothic 12 px |
| 9 | dictionnaire `{E00}`..`{E0A}` (mots fréquents : noms des filles, « ... ») |
| 10 | script : 10 200 messages |
| 11 | interface : 582 messages |
| 39 | police du bandeau (chiffres, jours 日月火水木金土, 円) |
| 50 / 51 | onglets du clavier de saisie du nom |
| 52 | libellés des stats |
| 67 | écran Relations : portraits + plaques de nom (15 tuiles par fille, plaque = tuiles 9-14) |
| 69 | écran Relations : libellés des lignes 愛情 / 興味 / 親密 / デート → LOVE / ÉLAN / LIEN / RDV |
| 55 | petite police du planning (⚠ cases 13 ？, 21-22 ◁▷, 28-31 main-curseur : à garder) |
| 87 | logo du titre (plan de fond 20×19, 122 tuiles ≤ 128) |
| 89-94 | lettrages en sprites de l'écran titre (descripteurs en fichier 0x19DC8) |

## Encodage du texte
- Entrée texte = table d'offsets `u32` (nombre = 1er offset / 4), puis messages en **codes 12 bits
  empaquetés** : 3 octets = 2 codes (`c1 = o0<<4 | o1>>4`, `c2 = (o1&15)<<8 | o2`).
- Code = numéro de glyphe dans la police (table : `tools/table.tbl`).
- Contrôles : `FFE` ligne, `FFC` attente, `FFD` page, `FFF` fin, `FFB` tabulation (12 px),
  `F00` nom, `F01` prénom, `F02` surnom, `F03`-`F08` façon dont Ruruna / Mizuki / Yumi / Momoyo /
  Mirei / Konoha appellent le héros, `F09` / `F0B` couleur, `E00`-`E0A` mot du dictionnaire.
- Au moment de l'affichage, le message est déplié dans un tampon RAM de **128 codes** (0x4290),
  sur 16 bits par code (octet haut, octet bas).

## Police latine et chasse variable
- Les glyphes latins (a-z, A-Z, 0-9, accents, ponctuation, espaces fins de 1 à 3 px et blancs de
  24 / 48 / 96 px) sont rendus depuis MS Gothic 12 px (`tools/police_fr.py`), comme la police du
  jeu, dans les cases libres 0x9BC..0xBFE.
- Avance du curseur : `0x211A28 add (0x428A),0x0C` → `call 0x800000`, qui lit la largeur du
  glyphe dans une table (1 octet par code) en 0x801000.
- Noms saisis : le clavier écrit des codes « clavier » (0xA3C.., avance 12) ; un crochet en
  0x211885 → 0x800040 les convertit en lettres étroites dans le tampon du nom.
- Suffixes collés aux noms (table 0x21A820) : 君 → « -kun », さん → « -san » (glyphes liés).

## Boîtes de dialogue (mesuré à l'écran)
- **144 px** par ligne (au-delà le moteur renvoie à la ligne), **136 px** pour la 4e ligne (l'icône
  d'attente ♥ commence vers 137 px), **4 lignes** par boîte, **128 codes** par message.
- Les lignes basses de certaines fenêtres d'appel s'arrêtent vers 130 px.
- `build.py` contrôle tout cela et refuse de construire s'il y a une erreur.

## Écran titre
- Logo latin redessiné en plan de fond (entrée 87, `tools/logo.py`).
- Lettrages « Appuie sur A ! / Nouvelle partie / Charger / Album » en sprites (`tools/titre_fr.py`).
- La surbrillance du menu supposait 16 sprites par option (`cp IY,0x10` en 0x20E067) : crochet
  0x8000A0 qui compare au vrai nombre de sprites (table 0x800090).
- Le clignotement cachait l'option en x=160 ; un lettrage de plus de 96 px repassait alors par x=0
  (un « e » fantôme) : on cache en y=160 (0x20DEA8).

## Interface graphique
- Bandeau : date jour/mois « 18/04 (D) » (routine 0x203F0D : jour et mois échangés, `月` → `/`,
  `日` effacé) ; jours de la semaine en une lettre (L M M J V S D) ; `円` → `¥` (`tools/hud_fr.py`).
- Planning (petite police proportionnelle 4×6 de l'entrée 55, tables 0x219538..), stats (entrée 52),
  onglets du clavier (`tools/planning_fr.py`, `stats_fr.py`, `clavier_fr.py`).
- Date des sauvegardes jour d'abord (0x2128FB / 0x21291C).

## Dates du rendez-vous (`tools/date_fr.py`, source `tools/asm/date_fr.asm`)
Le jeu écrivait mois, 月, jour, 日 avec des chiffres pleine chasse de 12 px (sub_211BE0).
La routine **DATE_FR** (CPU 0x800200) écrit « jour/mois » en chiffres étroits d'un seul tenant :
phrase et récapitulatif (« Rendez-vous le 18/4 » / « au matin ! ») et liste des jours.

## Générique (`tools/asm/centre_fr.asm`)
sub_21439B centrait chaque ligne à 12 px par code (x = 80 − n × 6), ce qui coupait les noms
latins. Le comptage (0x2143C6) est remplacé par **DEMI_LARGEUR** (CPU 0x800280), qui fait la
somme des vraies largeurs.

Les deux routines sont assemblées avec **AS** (Alfred Arnold, `cpu 96C141`) ; leurs octets sont
recopiés dans `date_fr.py` (le build vérifie que les codes de police n'ont pas bougé).

## Repères RAM (utiles pour tester)
| adresse | contenu |
|---|---|
| 0x45EB..0x45F0 | numéro de téléphone connu de chaque fille (2 = connu) |
| 0x46AA | jour de l'année (0 = 10/04 ; le jour 0x151 = mi-mars déclenche la fin) |
| 0x46B8 | argent, en centaines de yens |
