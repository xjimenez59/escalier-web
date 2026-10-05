#!/bin/sh
# Mise à jour automatique sur le NAS : récupère la dernière image publiée par GitHub
# et ne redémarre le conteneur que si elle a changé.
# À lancer par une tâche planifiée (cron) toutes les 10 minutes, par exemple :
#   */10 * * * * /share/Container/escalier-web/mise-a-jour.sh >> /share/Container/escalier-web/mise-a-jour.log 2>&1
set -eu
cd "$(dirname "$0")"
DOCKER=${DOCKER:-docker}
avant=$($DOCKER compose images -q escalier 2>/dev/null || true)
$DOCKER compose pull -q escalier
apres=$($DOCKER compose images -q escalier 2>/dev/null || true)
$DOCKER compose up -d escalier
if [ "$avant" != "$apres" ]; then
  echo "$(date '+%F %T') nouvelle image déployée"
  $DOCKER image prune -f >/dev/null
fi
