#!/usr/bin/env bash
# Provisiona Garage, l'object storage S3 dello stack: layout del nodo e chiave
# di accesso dell'applicazione. Idempotente: si puo' rieseguire su uno stack
# gia' provisionato.
#
# Perche' non e' un container di init: l'immagine di Garage non contiene una
# shell (nemmeno /bin/sh), quindi il bootstrap non puo' essere uno script
# eseguito dentro di essa. Si invocano i singoli comandi del binario con
# `docker compose exec`.
#
# Nessun bucket viene creato qui, ed e' voluto: l'applicazione crea un bucket
# per inquilino (`tenant-<id>` in shared/tasks/pipeline.py) con la CreateBucket
# di S3, e li rimuove in shared/tasks/maintenance.py. Per questo la chiave
# riceve il permesso --create-bucket, che in Garage e' negato per difetto. Un
# bucket fisso qui non lo userebbe nessuno.
set -euo pipefail

SVC="${GARAGE_SERVICE:-garage}"
KEY="${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY non impostata: esegui make bootstrap}"
SECRET="${MINIO_SECRET_KEY:?MINIO_SECRET_KEY non impostata: esegui make bootstrap}"

g() { docker compose exec -T "$SVC" /garage "$@" 2>&1; }

echo "garage: attendo che il nodo risponda"
for i in $(seq 1 60); do
  if g status >/dev/null 2>&1; then break; fi
  if [ "$i" = "60" ]; then echo "garage: il nodo non risponde dopo 120s" >&2; exit 1; fi
  sleep 2
done

# Il layout va assegnato una volta sola: senza, ogni chiamata risponde
# "Layout not ready" e l'applicazione prende AccessDenied.
if g layout show | grep -q "dc1"; then
  echo "garage: layout gia' assegnato"
else
  nid="$(g node id -q | tr -d '\r' | cut -d@ -f1 | tail -1)"
  echo "garage: assegno il nodo ${nid:0:16} alla zona dc1"
  g layout assign -z dc1 -c 1G "$nid" >/dev/null
  ver="$(g layout show | sed -n 's/.*version \([0-9][0-9]*\).*/\1/p' | tail -1)"
  g layout apply --version "${ver:-1}" >/dev/null
fi

# La chiave si importa solo se assente. Attenzione a non confondere un errore
# vero con "esiste gia'": un access key id fuori formato ("GK" + 12 byte
# esadecimali) viene rifiutato, e mascherarlo lascerebbe lo storage muto.
if g key info "$KEY" >/dev/null 2>&1; then
  echo "garage: la chiave $KEY c'era gia'"
else
  out="$(g key import "$KEY" "$SECRET" -n naso-app --yes)" || {
    echo "garage: importazione della chiave fallita." >&2
    echo "$out" | grep -v netapp >&2
    exit 1
  }
  echo "garage: chiave $KEY importata"
fi

g key allow --create-bucket "$KEY" >/dev/null
echo "garage: pronto, la chiave $KEY puo' creare i bucket per inquilino"
