import io

import pytest

from app import escalier
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
