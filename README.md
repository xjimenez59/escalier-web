# Escalier quart tournant : générateur de plans

Application web qui calcule un escalier quart tournant balancé sur crémaillères et produit un PDF de fabrication
(plan, perspective, fiches des marches, tracé des crémaillères, liste de débit).

## Lancer en local

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
flask --app app.web run            # http://127.0.0.1:5000
python -m app.escalier --help      # version ligne de commande
```

## Chaîne de publication

`git push` sur `main` → GitHub Actions lance les tests et publie l'image `ghcr.io/<utilisateur>/escalier-web:edge`.
`git tag v1.0.0 && git push origin v1.0.0` → publie `:1.0.0` et `:latest`, que le NAS déploie automatiquement.

## Mise en place (une seule fois)

### 1. GitHub
1. Créer le dépôt `escalier-web` (privé ou public) et y pousser ce dossier.
2. Après la première publication d'image : GitHub → ton profil → *Packages* → `escalier-web` →
   *Package settings* → passer la visibilité en **Public** (le plus simple : le NAS n'a alors pas besoin d'identifiants).
   Si tu veux garder l'image privée : sur le NAS, `docker login ghcr.io` avec un jeton GitHub (droit `read:packages`).

### 2. NAS QNAP (Container Station)
1. Créer le dossier `/share/Container/escalier-web` et y copier `compose.yaml` et `deploy/mise-a-jour.sh`.
   Dans `compose.yaml`, remplacer `GITHUB_UTILISATEUR` et, si besoin, le port `8087`.
2. Démarrer : Container Station → *Applications* → *Créer* (coller le `compose.yaml`), ou en SSH :
   `cd /share/Container/escalier-web && docker compose up -d`.
3. Mise à jour automatique : ajouter la ligne suivante à `/etc/config/crontab` (en SSH, admin), puis
   `crontab /etc/config/crontab && /etc/init.d/crond.sh restart` :
   ```
   */10 * * * * /share/Container/escalier-web/mise-a-jour.sh >> /share/Container/escalier-web/mise-a-jour.log 2>&1
   ```
   Si la commande `docker` n'est pas dans le PATH de cron, la préciser en tête de ligne :
   `DOCKER=/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker` (adapter le chemin).

### 3. Caddy
Ajouter le bloc de `deploy/Caddyfile.exemple` au Caddyfile (nom de domaine, adresse du NAS, mot de passe
optionnel), puis recharger Caddy.
