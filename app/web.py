"""Application web : formulaire de paramètres -> PDF des plans de l'escalier."""
import io
import os
from datetime import datetime

from flask import Flask, render_template, request, send_file

from . import escalier

app = Flask(__name__)
VERSION = os.environ.get("APP_VERSION", "dev")

# (nom du paramètre, libellé, type, min, max, pas, aide)
GROUPES = [
    ("La pièce et la trémie", [
        ("sens", "Sens du quart tournant", "choix", ["droite", "gauche"], None, None, "Vu depuis le bas de l'escalier, en montant."),
        ("hauteur", "Hauteur de sol fini à sol fini", float, 150, 400, 0.1, ""),
        ("plancher", "Épaisseur du plancher d'arrivée", float, 5, 50, 0.1, "Du dessous du chevêtre au sol fini."),
        ("long_depart", "Longueur le long du mur de départ", float, 80, 400, 0.1, "De l'angle des murs au nez de la première marche."),
        ("long_arrivee", "Longueur le long du mur d'arrivée", float, 100, 600, 0.1, "De l'angle des murs au chevêtre (bord de la trémie)."),
        ("tremie_largeur", "Largeur de la trémie", float, 50, 300, 0.1, "Mesurée depuis le mur d'arrivée."),
    ]),
    ("L'escalier", [
        ("nb_hauteurs", "Nombre de hauteurs de marche", int, 0, 30, 1, "0 = choix automatique selon Blondel."),
        ("balancement_debut", "Première marche balancée", int, 1, 29, 1, ""),
        ("balancement_fin", "Dernière marche balancée", int, 2, 29, 1, ""),
        ("largeur_marche", "Longueur utile des marches", float, 50, 150, 0.1, "Du jeu au mur jusqu'au bord côté jour."),
        ("jeu_mur", "Jeu entre marches et murs", float, 0, 3, 0.1, ""),
        ("debord_jour", "Débord des marches côté jour", float, 0, 6, 0.1, "Au-delà de la face arrière des crémaillères intérieures."),
        ("recouvrement", "Recouvrement des marches", float, 0, 6, 0.1, ""),
        ("echappee_mini", "Échappée minimale acceptée", float, 150, 250, 1, "Une alerte s'affiche en dessous."),
    ]),
    ("Bois et assemblages", [
        ("ep_marche", "Épaisseur des marches", float, 2, 8, 0.1, ""),
        ("ep_cremaillere", "Épaisseur des crémaillères", float, 2.5, 10, 0.1, ""),
        ("gorge_jour", "Gorge des crémaillères intérieures", float, 6, 25, 0.1, "Bois continu sous les entailles, perpendiculairement à la pente."),
        ("gorge_mur", "Gorge des crémaillères mur", float, 4, 25, 0.1, ""),
        ("poteau", "Section du poteau d'angle", float, 0, 20, 0.1, "0 = pas de poteau."),
        ("poteau_hauteur", "Hauteur du poteau d'angle", float, 0, 300, 1, "0 = juste ce qu'il faut pour porter les crémaillères."),
        ("soutien_largeur", "Largeur du bastaing de soutien", float, 5, 40, 0.1, ""),
        ("rive_basse", "Rive basse des crémaillères", "choix", ["droite", "decoupee"], None, None, "« droite » : face inférieure du brut conservée."),
        ("fixation_haut", "Fixation en haut", "choix", ["chevetre", "talon"], None, None, "« chevetre » : boulonnée sur la face du chevêtre."),
        ("ancrage", "Longueur d'ancrage sur le chevêtre", float, 5, 30, 0.1, ""),
        ("talon", "Longueur du talon (fixation « talon »)", float, 0, 20, 0.1, ""),
    ]),
]


def valeurs_defaut():
    P = escalier.parse_args([])
    v = dict(vars(P))
    v["balancement_debut"], v["balancement_fin"] = P.balancement
    return v


def lire_formulaire(form):
    """Construit les paramètres à partir du formulaire ; renvoie (Namespace, erreurs)."""
    P = escalier.parse_args([])
    v = valeurs_defaut()
    erreurs = []
    for _, champs in GROUPES:
        for nom, libelle, typ, a, b, _, _ in champs:
            brut = form.get(nom, "").strip().replace(",", ".")
            if brut == "":
                continue
            if typ == "choix":
                if brut not in a:
                    erreurs.append(f"{libelle} : valeur inconnue.")
                else:
                    v[nom] = brut
                continue
            try:
                val = typ(float(brut)) if typ is int else float(brut)
            except ValueError:
                erreurs.append(f"{libelle} : nombre attendu.")
                continue
            if not (a <= val <= b):
                erreurs.append(f"{libelle} : entre {a} et {b}.")
                continue
            v[nom] = val
    for nom in vars(P):
        if nom in v:
            setattr(P, nom, v[nom])
    P.balancement = [int(v["balancement_debut"]), int(v["balancement_fin"])]
    return P, v, erreurs


@app.get("/")
def index():
    return render_template("index.html", groupes=GROUPES, v=valeurs_defaut(), erreurs=[], version=VERSION)


@app.post("/")
def generer():
    P, v, erreurs = lire_formulaire(request.form)
    if not erreurs:
        try:
            E = escalier.Escalier(P)
        except escalier.EscalierErreur as e:
            erreurs.append(str(e))
    if erreurs:
        return render_template("index.html", groupes=GROUPES, v=v, erreurs=erreurs, version=VERSION), 400
    buf = io.BytesIO()
    escalier.build_pdf(E, buf)
    buf.seek(0)
    nom = f"escalier_{P.sens}_{datetime.now():%Y%m%d_%H%M}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=False, download_name=nom)


@app.get("/sante")
def sante():
    return {"etat": "ok", "version": VERSION}
