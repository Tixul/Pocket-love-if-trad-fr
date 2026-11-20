; Date « 18/4 » d'un seul tenant, en chiffres étroits (chasse variable), pour les phrases du
; rendez-vous. Remplace l'appel jour (sub_211BE0, chiffres pleine chasse de 12 px alignés à droite)
; + « / » + mois + case vide du jeu japonais.
;
; Appel (8 octets poussés, nettoyés par l'appelant) :
;   pushw jour ; pushw mois ; pushw x ; pushw (y | drapeau << 8) ; call DATE_FR
; Assemblage : asl -cpu 96C141 date_fr.asm ; p2bin date_fr.p (voir tools/date_fr.py)

        cpu     96C141
        maxmode on
        org     800200h

CHIFFRE0 equ    09F7h           ; code police du « 0 » étroit (police_fr)
BARRE   equ     0A2Ah           ; code police du « / » étroit
DESSINE equ     211A3Bh         ; sub_211A3B (tampon de codes 16 bits, x, y, drapeau)

DATE_FR:
        push    xiz
        push    xde
        push    xbc
        push    xhl
        lda     xsp,(xsp-16)    ; tampon : 16 octets
        ; pile : +0 tampon, +16 xhl, +20 xbc, +24 xde, +28 xiz, +32 retour,
        ;        +36 y|drapeau, +38 x, +40 mois, +42 jour
        lda     xde,(xsp+0)
        ld      wa,(xsp+42)
        call    NOMBRE
        ld      bc,BARRE
        ld      (xde),b
        ld      (xde+1),c
        inc     2,xde
        ld      wa,(xsp+40)
        call    NOMBRE
        ld      bc,0FFFh
        ld      (xde),b
        ld      (xde+1),c
        ; sub_211A3B(tampon, x, y, drapeau)
        ld      wa,(xsp+36)
        ld      c,w
        ld      b,0
        push    bc              ; drapeau
        ld      w,0
        push    wa              ; y
        ld      wa,(xsp+42)     ; x (+38 avant les 2 poussées)
        push    wa
        lda     xbc,(xsp+6)     ; tampon
        push    xbc
        call    DESSINE
        lda     xsp,(xsp+10)
        lda     xsp,(xsp+16)
        pop     xhl
        pop     xbc
        pop     xde
        pop     xiz
        ret

; WA = nombre, XDE = où écrire ; écrit les chiffres (poids fort d'abord), avance XDE.
NOMBRE:
        ld      hl,0
NB1:    extz    xwa
        div     xwa,10          ; WA = quotient, mot haut = reste
        push    xwa
        pop     bc              ; quotient ; le reste reste sur la pile
        ld      wa,bc
        inc     1,hl
        cp      wa,0
        jr      nz,NB1
NB2:    pop     bc
        add     bc,CHIFFRE0
        ld      (xde),b
        ld      (xde+1),c
        inc     2,xde
        dec     1,hl
        cp      hl,0            ; dec 16 bits ne pose pas les drapeaux
        jr      nz,NB2
        ret
