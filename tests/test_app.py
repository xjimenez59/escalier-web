import io
import zipfile

import pytest

from app import escalier, export3d
from app.geometrie import pip
from app.modele3d import scene, solide
from app.web import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_moteur_valeurs_par_defaut():
    E = escalier.Escalier(escalier.parse_args([]))
    assert E.n == 15
    assert abs(E.h - 290 / 15) < 1e-9
    assert 60 <= E.blondel <= 64.5
    assert E.echappee > 190


@pytest.mark.parametrize("args", [[], ["--sens", "gauche"], ["--rive-basse", "decoupee"], ["--fixation-haut", "talon"],
                                  ["--poteau-hauteur", "200"], ["--balancement", "3", "10"],
                                  ["--largeur-depart", "80", "--largeur-arrivee", "100"],
                                  ["--largeur-depart", "100", "--largeur-arrivee", "80"],
                                  ["--ep-contremarche", "1.2"],
                                  ["--ep-contremarche", "1.2", "--sens", "gauche"],
                                  ["--ep-contremarche", "1.2", "--largeur-depart", "80", "--largeur-arrivee", "100"],
                                  ["--ep-contremarche", "1.2", "--poteau", "0"]])
def test_pdf_genere(args):
    E = escalier.Escalier(escalier.parse_args(args))
    buf = io.BytesIO()
    escalier.build_pdf(E, buf)
    assert buf.getvalue()[:4] == b"%PDF"


def test_largeur_arrivee_zero_identique_au_depart():
    E1 = escalier.Escalier(escalier.parse_args([]))
    E2 = escalier.Escalier(escalier.parse_args(["--largeur-arrivee", "0"]))
    assert E1.JRd == E2.JRd == E1.JRa == E2.JRa
    assert E1.n == E2.n and abs(E1.h - E2.h) < 1e-9


def test_largeur_depart_asymetrique():
    E = escalier.Escalier(escalier.parse_args(["--largeur-depart", "80", "--largeur-arrivee", "100"]))
    assert E.Wd == 80 and E.Wa == 100
    assert E.JRd < E.JRa
    assert E.collet_mini > 0


def test_sans_contremarche_par_defaut():
    E = escalier.Escalier(escalier.parse_args([]))
    assert E.RISERS == {}


def test_contremarches_une_par_hauteur():
    E = escalier.Escalier(escalier.parse_args(["--ep-contremarche", "1.2"]))
    assert len(E.RISERS) == E.n
    # la première (sol) n'a ni rainure ni pré-perçages (tasseaux collés), la dernière (chevêtre) n'a pas de rainure
    assert not E.RISERS[0]['percage'] and not E.RISERS[0]['rainure']
    assert E.RISERS[E.n-1]['percage'] and not E.RISERS[E.n-1]['rainure']
    for i in range(1, E.n-1):
        assert E.RISERS[i]['percage'] and E.RISERS[i]['rainure']
    for i in E.RISERS:
        L, H, Htot, holes = E.riser_local(i)
        assert L > 0 and H > 0 and Htot >= H
    # chaque panneau (hors le dernier, contre le chevêtre) est entièrement au-delà du pli des deux
    # crémaillères qu'il touche : leur bois est plein jusqu'en haut du panneau à cet endroit précis
    # (vérifié avec `backed`, pas top_at qui peut être trop optimiste près d'un coin), donc appuyé
    # sur du bois plein plutôt que posé dans le vide.
    for i in range(E.n - 1):
        r = E.RISERS[i]
        p0, nr = E.line_normal(i)
        back = E.contremarche_offset(i)
        assert back is not None
        (_, mur_key), (_, jour_key) = E.riser_pair(p0, nr, back)
        assert E.backed(mur_key, r['a'], r['z_haut'])
        assert E.backed(jour_key, r['b'], r['z_haut'])


CONFIG_UTILISATEUR = ["--sens", "gauche", "--hauteur", "249", "--long-depart", "200", "--long-arrivee", "255",
                      "--tremie-largeur", "300", "--largeur-depart", "80", "--largeur-arrivee", "100"]


def collisions(E, pas=1.0, marge=0.3):
    """Points de chaque marche situés au-dessus d'une crémaillère plus haute que la marche (la marche
    serait alors posée dans le bois de la crémaillère)."""
    zones = {'mur_dep': (0, E.WL, 0, E.Y0), 'mur_arr': (E.WL, E.XE, 0, E.WL),
             'int_bas': (E.INx, E.JXx, E.INy, E.Y0), 'int_haut': (E.JXx, E.XE, E.INy, E.JXy)}
    out = []
    for m, poly in E.TREADS.items():
        z = m*E.h - E.EP
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        x = min(xs)
        while x <= max(xs):
            y = min(ys)
            while y <= max(ys):
                if pip((x, y), poly):
                    for k, (x0, x1, y0, y1) in zones.items():
                        if x0+marge < x < x1-marge and y0+marge < y < y1-marge and E.backed(k, (x, y), z+0.3):
                            out.append((m, k, x, y))
                y += pas
            x += pas
    return out


@pytest.mark.parametrize("args", [[], ["--long-depart", "125"], ["--long-arrivee", "115"], ["--largeur-depart", "95"],
                                  CONFIG_UTILISATEUR, CONFIG_UTILISATEUR + ["--long-arrivee", "115"],
                                  CONFIG_UTILISATEUR + ["--debord-jour", "0"]])
def test_aucune_marche_dans_une_cremaillere(args):
    # y compris les cas de double contact près du coin (crémaillère qui remonte dans le carré du coin)
    E = escalier.Escalier(escalier.parse_args(args))
    assert collisions(E) == []


def test_parcours_tourne_aux_coins():
    E = escalier.Escalier(escalier.parse_args(CONFIG_UTILISATEUR))
    # marche 5, côté jour : arête extérieure d'int_bas, coin, puis arête extérieure d'int_haut
    assert (E.JRd, E.JRa) in [tuple(round(c, 9) for c in p) for p in E.TREADS[5]]
    # marche 6, côté mur : mur de départ, coin de la pièce, puis mur d'arrivée
    assert (E.WR, E.WR) in E.TREADS[6]
    assert "on tourne au coin" in E.trace_marche(5)


def test_ecretage_du_bout_de_cremaillere():
    # le dernier palier d'int_bas (2,4 cm, dans le carré du coin) est supprimé : int_haut porte déjà
    # les deux marches concernées ; la marche 3 n'a plus à le contourner
    E = escalier.Escalier(escalier.parse_args(["--largeur-depart", "95"]))
    assert 'int_bas' in E.ECRETE
    assert len(E.TREADS[3]) == 7
    # sans effet sur la config par défaut et celle de l'utilisateur
    for args in ([], CONFIG_UTILISATEUR):
        assert escalier.Escalier(escalier.parse_args(args)).ECRETE == {}


@pytest.mark.parametrize("args", [[], ["--long-arrivee", "115"], CONFIG_UTILISATEUR])
def test_pointe_cote_jour_limitee_au_recouvrement(args):
    # le bout du nez côté jour ne dépasse pas la face avant de sa crémaillère de plus que le
    # recouvrement, mesuré le long de celle-ci (sinon pointe de plus de 12 cm avec --long-arrivee 115)
    assert "Pointe côté jour recoupée" in escalier.Escalier(escalier.parse_args(["--long-arrivee", "115"])).trace_marche(9)
    E = escalier.Escalier(escalier.parse_args(args))
    for m, poly in E.TREADS.items():
        z = m*E.h - E.EP
        for k in ('int_bas', 'int_haut'):
            cr = E.CR[k]; o = E.JRd if k == 'int_bas' else E.JRa
            seg = [s_ for s_ in E.PAL[k] if abs(s_[0] - z) < 1e-6]
            pts = [p for p in poly if abs(p[cr.axe] - o) < 1e-6]
            # seulement les vraies pointes : la ligne de coupe recoupe le nez (son autre bout est au-delà)
            if seg and pts and cr.d_of(E.LINES[m-1][1]) > seg[0][1] - E.REC:
                assert min(cr.d_of(p) for p in pts) >= seg[0][1] - E.REC - escalier.POINTE_MINI - 0.01


def test_alerte_palier_saute():
    E = escalier.Escalier(escalier.parse_args(["--long-depart", "125"]))
    assert any("aucun palier pour la marche 3" in a for a in E.alertes)
    assert not any("aucun palier" in a for a in escalier.Escalier(escalier.parse_args([])).alertes)


def test_rainure_trop_profonde_alerte():
    E = escalier.Escalier(escalier.parse_args(["--ep-contremarche", "1.2", "--profondeur-rainure", "3", "--ep-marche", "4"]))
    assert any("rainure" in a.lower() for a in E.alertes)


def test_balancement_impossible():
    with pytest.raises(escalier.EscalierErreur):
        escalier.Escalier(escalier.parse_args(["--balancement", "8", "11"]))


def test_page_formulaire(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Générer le PDF" in r.get_data(as_text=True)


def test_post_pdf(client):
    r = client.post("/", data={"sens": "gauche", "hauteur": "290"})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"


def test_post_pdf_contremarches(client):
    r = client.post("/", data={"ep_contremarche": "1.2", "profondeur_rainure": "0.8"})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"


def test_post_erreur(client):
    r = client.post("/", data={"balancement_debut": "8", "balancement_fin": "11"})
    assert r.status_code == 400
    assert "balancement" in r.get_data(as_text=True).lower()


def test_post_hors_bornes(client):
    r = client.post("/", data={"hauteur": "5000"})
    assert r.status_code == 400


def test_sante(client):
    assert client.get("/sante").json["etat"] == "ok"


def test_get_3d(client):
    r = client.get("/3d", query_string={"sens": "gauche"})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "OrbitControls" in body
    assert '"positions"' in body


def test_get_3d_contremarches(client):
    r = client.get("/3d", query_string={"ep_contremarche": "1.2"})
    assert r.status_code == 200


def test_get_3d_erreur(client):
    r = client.get("/3d", query_string={"balancement_debut": "8", "balancement_fin": "11"})
    assert r.status_code == 400
    assert "balancement" in r.get_data(as_text=True).lower()


def test_export3d_zip(client):
    r = client.get("/export3d.zip", query_string={"sens": "gauche"})
    assert r.status_code == 200
    assert r.mimetype == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.get_data()))
    assert set(z.namelist()) == {"escalier.obj", "escalier.mtl"}
    obj_text = z.read("escalier.obj").decode("utf-8")
    assert "mtllib escalier.mtl" in obj_text
    assert "usemtl" in obj_text
    assert "\nv " in obj_text
    assert "\nf " in obj_text


def test_export3d_zip_hors_bornes(client):
    r = client.get("/export3d.zip", query_string={"hauteur": "5000"})
    assert r.status_code == 400


def test_scene_to_threejs_structure():
    E = escalier.Escalier(escalier.parse_args(["--ep-contremarche", "1.2"]))
    d = export3d.scene_to_threejs(E)
    assert len(d["positions"]) % 9 == 0   # multiples de 3 sommets * 3 coordonnées
    assert len(d["positions"]) == len(d["colors"])
    assert len(d["positions"]) > 0


def test_scene_to_obj_materiaux():
    E = escalier.Escalier(escalier.parse_args(["--ep-contremarche", "1.2"]))
    obj_text, mtl_text = export3d.scene_to_obj(E)
    assert mtl_text.count("newmtl") >= 2
    assert obj_text.count("\nf ") > 0


def test_solide_sans_subdivision_ni_ecart():
    """Le modèle exact (visionneuse/export) n'a ni la subdivision ni l'écart EPS_Z propres au
    rendu PDF : beaucoup moins de faces, et les contremarches vont jusqu'à leur vraie hauteur."""
    E = escalier.Escalier(escalier.parse_args(["--ep-contremarche", "1.2"]))
    faces_pdf = scene(E)
    faces_exact = solide(E)
    assert len(faces_exact) < len(faces_pdf)
    assert all(len(f) == 4 for f in faces_exact)  # jamais de plancher/chevêtre (slab)
    assert all(isinstance(f[2], str) and f[2].startswith("#") for f in faces_exact)
