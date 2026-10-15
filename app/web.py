"""Application web : formulaire de paramètres -> PDF des plans de l'escalier."""
import io
import os
import zipfile
from datetime import datetime

from flask import Flask, render_template, request, send_file

from . import cnc, escalier, export3d

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
        ("largeur_depart", "Longueur utile des marches, volée de départ", float, 50, 150, 0.1, "Du jeu au mur jusqu'au bord côté jour."),
        ("largeur_arrivee", "Longueur utile des marches, volée d'arrivée", float, 0, 150, 0.1, "0 = même longueur que la volée de départ."),
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
    ("Contremarches (optionnel)", [
        ("ep_contremarche", "Épaisseur des contremarches", float, 0, 3, 0.1, "0 = pas de contremarches."),
        ("profondeur_rainure", "Profondeur de la rainure", float, 0.2, 2, 0.1,
         "Dans la face inférieure de la marche du dessus, pour loger le haut de la contremarche."),
    ]),
    ("Fabrication CNC (optionnel) : machine en mm, mm/min, tr/min", [
        ("cnc_zone_x", "Zone utile en X (mm)", float, 200, 3000, 1, "WorkBee 1510 : environ 824."),
        ("cnc_zone_y", "Zone utile en Y (mm)", float, 200, 3000, 1, "WorkBee 1510 : environ 1280."),
        ("cnc_avance_max", "Avance maxi en XY (mm/min)", float, 300, 10000, 10, "Au-delà de 2500, une WorkBee risque de perdre des pas."),
        ("cnc_broche_min", "Vitesse de broche mini (tr/min)", float, 1000, 30000, 100, ""),
        ("cnc_broche_max", "Vitesse de broche maxi (tr/min)", float, 5000, 60000, 100, ""),
        ("cnc_materiau", "Matériau", "choix", ["resineux", "feuillu_tendre", "feuillu_dur", "contreplaque", "mdf"], None, None,
         "Sert à calculer l'avance de la fraise."),
        ("cnc_fraise_diam", "Fraise principale : diamètre (mm)", float, 2, 12, 0.1, "Bout plat, carbure, hélice montante : rainures des contremarches."),
        ("cnc_fraise_dents", "Fraise principale : nombre de dents", int, 1, 4, 1, ""),
        ("cnc_fraise_coupe", "Fraise principale : longueur de coupe (mm)", float, 5, 60, 1, "Au moins la profondeur de la rainure."),
        ("cnc_fraise_trous", "Fraise de 3 mm pour les pré-trous", "choix", ["non", "oui"], None, None,
         "« non » : les pré-trous sont seulement pointés (gravés), à percer à la main."),
        ("cnc_diam_trou", "Pré-trous des contremarches : diamètre (mm)", float, 1, 8, 0.1, "Environ les deux tiers du diamètre de la vis."),
        ("cnc_prof_trou", "Pré-trous des contremarches : profondeur (mm)", float, 3, 60, 1, "Depuis le dessous de la marche ; trous borgnes."),
        ("cnc_prof_gravure", "Profondeur de la gravure des contours (mm)", float, 0.1, 2, 0.1, "Fraise à graver en V."),
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
    E, err = escalier_depuis(request.form)
    if err: return err
    buf = io.BytesIO()
    escalier.build_pdf(E, buf)
    buf.seek(0)
    nom = f"escalier_{E.P.sens}_{datetime.now():%Y%m%d_%H%M}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=False, download_name=nom)


def escalier_depuis(args):
    """Calcule l'escalier à partir d'un formulaire ou d'une query string : (E, None) ou (None, page d'erreur 400)."""
    P, v, erreurs = lire_formulaire(args)
    if not erreurs:
        try:
            return escalier.Escalier(P), None
        except escalier.EscalierErreur as e:
            erreurs.append(str(e))
    return None, (render_template("index.html", groupes=GROUPES, v=v, erreurs=erreurs, version=VERSION), 400)


def plan_cnc_depuis(args):
    """(E, plan, None) ou (None, None, page d'erreur 400) : escalier puis plan de fabrication CNC."""
    E, err = escalier_depuis(args)
    if err is None:
        try:
            return E, cnc.plan_cnc(E), None
        except escalier.EscalierErreur as e:
            _, v, _ = lire_formulaire(args)
            return None, None, (render_template("index.html", groupes=GROUPES, v=v, erreurs=[str(e)], version=VERSION), 400)
    return None, None, err


@app.get("/3d")
def visionneuse3d():
    E, err = escalier_depuis(request.args)
    if err: return err
    return render_template("visionneuse.html", donnees=export3d.scene_to_threejs(E), requete=request.query_string.decode(), version=VERSION)


@app.get("/export3d.zip")
def export3d_zip():
    E, err = escalier_depuis(request.args)
    if err: return err
    obj_text, mtl_text = export3d.scene_to_obj(E)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("escalier.obj", obj_text)
        z.writestr("escalier.mtl", mtl_text)
    buf.seek(0)
    nom = f"escalier_3d_{E.P.sens}_{datetime.now():%Y%m%d_%H%M}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=nom)


@app.get("/cnc")
def recapitulatif_cnc():
    """Récapitulatif de la fabrication CNC (pièces, durées, alertes) avant de télécharger les fichiers."""
    E, plan, err = plan_cnc_depuis(request.args)
    if err: return err
    return render_template("cnc.html", plan=plan, E=E, duree=cnc.duree_texte, requete=request.query_string.decode(), version=VERSION)


@app.get("/gcode.zip")
def gcode_zip():
    E, plan, err = plan_cnc_depuis(request.args)
    if err: return err
    nom = f"escalier_cnc_{E.P.sens}_{datetime.now():%Y%m%d_%H%M}.zip"
    return send_file(cnc.zip_cnc(plan, E), mimetype="application/zip", as_attachment=True, download_name=nom)


@app.get("/sante")
def sante():
    return {"etat": "ok", "version": VERSION}
