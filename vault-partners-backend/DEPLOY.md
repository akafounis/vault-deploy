# Deploying to Google Cloud Run

## Prerequisites
- Google Cloud account with billing enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed
- Docker installed locally

---

## 1. First-time setup

```bash
# Login and set your project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable sqladmin.googleapis.com   # only if using Cloud SQL
```

---

## 2. Test Docker locally first

```bash
cd vault-partners

# Build
docker build -t vault-partners .

# Run locally (SQLite, no email)
docker run -p 8080:8080 \
  -e SECRET_KEY=my-local-secret-key \
  -e DATABASE_URL=sqlite:////app/data/vault.db \
  -e BASE_URL=http://localhost:8080 \
  vault-partners

# Or use docker-compose (easier, includes volumes)
docker-compose up --build
```

Visit http://localhost:8080 — then run the seed script inside the container:
```bash
docker-compose exec web python seed.py
```

---

## 3. Push image to Google Artifact Registry

```bash
# Create a repository
gcloud artifacts repositories create vault-partners \
  --repository-format=docker \
  --location=europe-west1 \
  --description="Vault Partners app"

# Configure Docker auth
gcloud auth configure-docker europe-west1-docker.pkg.dev

# Build and tag for GCR
docker build -t europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest .

# Push
docker push europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest
```

---

## 4. Deploy to Cloud Run

```bash
gcloud run deploy vault-partners \
  --image europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars="SECRET_KEY=YOUR_LONG_RANDOM_SECRET" \
  --set-env-vars="DATABASE_URL=sqlite:////app/data/vault.db" \
  --set-env-vars="BASE_URL=https://vault-partners.eu" \
  --set-env-vars="SMTP_HOST=smtp.gmail.com" \
  --set-env-vars="SMTP_PORT=587" \
  --set-env-vars="SMTP_USER=your@gmail.com" \
  --set-env-vars="SMTP_PASSWORD=your-app-password" \
  --set-env-vars="EMAIL_FROM=noreply@vault-partners.eu"
```

Cloud Run will give you a URL like `https://vault-partners-xxxx-ew.a.run.app`.

---

## 5. Point your domain (vault-partners.eu)

In Cloud Run console → your service → **Custom Domains** → **Add mapping**:
- Add `vault-partners.eu` and `www.vault-partners.eu`
- Google gives you DNS records to add in your domain registrar
- SSL is automatic

---

## 6. Important: File Storage Warning

Cloud Run containers are **stateless** — the filesystem resets on each deploy or scale event.

**For production, use Google Cloud Storage for uploads:**

### Option A — Quick (SQLite + GCS for files)
Use the `google-cloud-storage` Python library and save uploads to a GCS bucket instead of local disk. Set a `GCS_BUCKET` env var.

### Option B — Full managed DB (recommended)
Use **Cloud SQL (PostgreSQL)**:
```bash
# Create instance
gcloud sql instances create vault-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=europe-west1

# Create database and user
gcloud sql databases create vaultdb --instance=vault-db
gcloud sql users create vaultuser --instance=vault-db --password=YOUR_DB_PASSWORD

# Then update DATABASE_URL in Cloud Run:
# DATABASE_URL=postgresql://vaultuser:YOUR_DB_PASSWORD@/vaultdb?host=/cloudsql/YOUR_PROJECT:europe-west1:vault-db
```

---

## 7. Redeploy after code changes

```bash
# Rebuild and push
docker build -t europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest .
docker push europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest

# Redeploy (Cloud Run picks up the new image automatically if using :latest)
gcloud run deploy vault-partners \
  --image europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/vault-partners/app:latest \
  --region europe-west1
```

---

## Quick reference — environment variables

| Variable        | Description                        | Example                          |
|-----------------|------------------------------------|----------------------------------|
| `SECRET_KEY`    | Session signing key (keep secret!) | any 32+ char random string       |
| `DATABASE_URL`  | DB connection string               | `sqlite:////app/data/vault.db`   |
| `BASE_URL`      | Public URL of your site            | `https://vault-partners.eu`      |
| `SMTP_HOST`     | Email server                       | `smtp.gmail.com`                 |
| `SMTP_PORT`     | Email port                         | `587`                            |
| `SMTP_USER`     | Email login                        | `you@gmail.com`                  |
| `SMTP_PASSWORD` | Email password / app password      | Gmail app password               |
| `PORT`          | HTTP port (set automatically by Cloud Run) | `8080`                  |
