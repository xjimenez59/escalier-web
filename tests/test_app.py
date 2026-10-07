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
                                  ["--largeur-depart", "100", "--largeur-arrivee", "80"]])
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


def test_post_erreur(client):
    r = client.post("/", data={"balancement_debut": "8", "balancement_fin": "11"})
    assert r.status_code == 400
    assert "balancement" in r.get_data(as_text=True).lower()


def test_post_hors_bornes(client):
    r = client.post("/", data={"hauteur": "5000"})
    assert r.status_code == 400


def test_sante(client):
    assert client.get("/sante").json["etat"] == "ok"
