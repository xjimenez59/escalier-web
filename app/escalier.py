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

Mise au point : ajouter `--trace-marche N` affiche le détail du tracé de la marche N (parcours
des arêtes, points 1 à 6) au lieu de produire le PDF.

Fabrication CNC : `--gcode DOSSIER` écrit dans DOSSIER les fichiers G-code et le guide de fraisage
(app/cnc.py) au lieu de produire le PDF.

Toutes les cotes sont en centimètres.
"""
import os
import sys

from .geometrie import EscalierErreur, Escalier, parse_args, fr, POINTE_MINI
from .pdf import build_pdf

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # --trace-marche N : affiche le détail du tracé de la marche N (mise au point), sans produire
    # le PDF ; option de la seule ligne de commande, pas un paramètre de l'escalier
    trace = None
    if "--trace-marche" in argv:
        i = argv.index("--trace-marche"); trace = int(argv[i+1]); del argv[i:i+2]
    gcode = None
    if "--gcode" in argv:
        i = argv.index("--gcode"); gcode = argv[i+1]; del argv[i:i+2]
    P = parse_args(argv)
    try:
        E = Escalier(P)
    except EscalierErreur as e:
        sys.exit(str(e))
    if trace is not None:
        print(E.trace_marche(trace))
        return
    if gcode is not None:
        from . import cnc
        try:
            plan = cnc.plan_cnc(E)
        except EscalierErreur as e:
            sys.exit(str(e))
        os.makedirs(gcode, exist_ok=True)
        for pc in plan.pieces:
            for g in pc.programmes:
                with open(os.path.join(gcode, g.fichier), "w", encoding="ascii", newline="\n") as f: f.write(g.texte())
        with open(os.path.join(gcode, "GUIDE_FRAISAGE.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(cnc.guide_fraisage(plan, E))
        print(f"{gcode} : {sum(len(pc.programmes) for pc in plan.pieces)} fichiers G-code et GUIDE_FRAISAGE.txt, "
              f"durée estimée {cnc.duree_texte(plan.duree_totale)}")
        for a in plan.alertes: print("Attention :", a)
        return
    build_pdf(E, P.sortie)
    print(f"{P.sortie} : {E.n} hauteurs de {E.h:.2f} cm, giron {E.g:.2f} cm, 2h+g = {E.blondel:.1f}, "
          f"échappée {E.echappee:.1f} cm")
    for a in E.alertes: print("Attention :", a)

if __name__ == "__main__":
    main()
