#!/usr/bin/env bash
# Repo kokunden calistirin:  bash backend/deploy.sh
set -euo pipefail
PROJECT=${GOOGLE_CLOUD_PROJECT:?}
REGION=${REGION:-europe-west4}
SERVICE=meetmind-api

BUCKET=${GCS_BUCKET:-$PROJECT-meetmind-stt}
gcloud services enable run.googleapis.com speech.googleapis.com storage.googleapis.com artifactregistry.googleapis.com --project "$PROJECT"

# gecici ses objeleri icin bucket (yoksa olustur) + 1 gunluk otomatik silme
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT" --location "$REGION" --uniform-bucket-level-access
cat > /tmp/lc.json <<'JSON'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":1}}]}
JSON
gcloud storage buckets update "gs://$BUCKET" --lifecycle-file=/tmp/lc.json

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated \
  --timeout 3600 --memory 1Gi --cpu 1 \
  --no-cpu-throttling \
  --min-instances 0 --max-instances 3 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,STT_LOCATION=$REGION,GCS_BUCKET=$BUCKET,STT_DIARIZE=${STT_DIARIZE:-0},LLM_MODEL=${LLM_MODEL:-claude-opus-5}" \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-key:latest,SUPABASE_JWT_SECRET=supabase-jwt-secret:latest"

# --no-cpu-throttling: /process 202 dondukten sonra arka plan isi (STT 20-40 dk) devam etsin diye SART.
# Not: --allow-unauthenticated acik cunku yetki JWT ile server.py icinde dogrulaniyor.
# Sirlar: gcloud secrets create anthropic-key --data-file=- <<< "$ANTHROPIC_API_KEY"  (her biri icin)
