# Windows PowerShell deploy. Repo kokunden:  .\backend\deploy.ps1 -ProjectId PROJE_ID
param([Parameter(Mandatory=$true)][string]$ProjectId, [string]$Region="europe-west4")
$Bucket = "$ProjectId-meetmind-stt"
gcloud config set project $ProjectId
gcloud services enable run.googleapis.com speech.googleapis.com storage.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
gcloud storage buckets describe "gs://$Bucket" 2>$null
if ($LASTEXITCODE -ne 0) { gcloud storage buckets create "gs://$Bucket" --location=$Region --uniform-bucket-level-access }
gcloud run deploy meetmind-api --source . --region $Region --allow-unauthenticated `
  --timeout 3600 --memory 1Gi --cpu 1 --no-cpu-throttling --min-instances 0 --max-instances 3 `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$ProjectId,STT_LOCATION=$Region,GCS_BUCKET=$Bucket,STT_DIARIZE=0,LLM_MODEL=claude-opus-5" `
  --set-secrets "ANTHROPIC_API_KEY=anthropic-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-key:latest,SUPABASE_JWT_SECRET=supabase-jwt-secret:latest"
