; Générique : centrage d'une ligne à la largeur RÉELLE (chasse variable).
; sub_21439B comptait les codes (hors contrôles 0x0Fxx) et faisait x = 80 - n*12/2.
; Appelée à la place de cette boucle (0x2143C6) : XIZ = tampon de codes 16 bits (hi, lo),
; renvoie WA = largeur / 2 ; XBC et XDE conservés.
; Assemblage : asl -cpu 96C141 centre_fr.asm ; p2bin centre_fr.p (voir tools/date_fr.py)

        cpu     96C141
        maxmode on
        org     800280h

LARGEURS equ    801000h         ; table des largeurs (1 octet par code)

DEMI_LARGEUR:
        push    xbc
        push    xde
        ld      xbc,xiz
        ld      de,0
BOUCLE: ld      w,(xbc)
        ld      a,(xbc+1)
        cp      wa,0FFFh
        jr      z,FIN
        cp      w,0Fh           ; 0x0Fxx = contrôle (couleur…) : pas de largeur
        jr      z,SUIVANT
        extz    xwa
        add     xwa,LARGEURS
        ld      a,(xwa)
        extz    wa
        add     de,wa
SUIVANT:
        inc     2,xbc
        jr      BOUCLE
FIN:    ld      wa,de
        srl     1,wa
        pop     xde
        pop     xbc
        ret
