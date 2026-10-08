#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Escalier quart tournant balancé, marches posées sur crémaillères.
Point d'entrée en ligne de commande ; réexporte l'API utilisée par app/web.py et les tests.
Le calcul est dans app/geometrie.py, le PDF dans app/pdf.py, le modèle 3D dans
app/modele3d.py, son rendu dans app/rendu3d.py.

Dépendance : reportlab  (pip install reportlab)

Exemple :
    python3 -m app.escalier --sens droite --hauteur 290 --plancher 22 \
        --long-depart 160 --long-arrivee 260 --tremie-largeur 100 \
        --balancement 3 11 --ep-cremaillere 4.5 --ep-marche 4 -o escalier.pdf

Toutes les cotes sont en centimètres.
"""
import sys

from .geometrie import EscalierErreur, Escalier, parse_args, fr
from .pdf import build_pdf

def main(argv=None):
    P = parse_args(argv)
    try:
        E = Escalier(P)
    except EscalierErreur as e:
        sys.exit(str(e))
    build_pdf(E, P.sortie)
    print(f"{P.sortie} : {E.n} hauteurs de {E.h:.2f} cm, giron {E.g:.2f} cm, 2h+g = {E.blondel:.1f}, "
          f"échappée {E.echappee:.1f} cm")
    for a in E.alertes: print("Attention :", a)

if __name__ == "__main__":
    main()
