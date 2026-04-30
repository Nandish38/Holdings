# Firebase Hosting + Cloud Run (free-ish public hosting)

This deploys Vaultboard publicly using:

- **Cloud Run**: runs the Streamlit container
- **Firebase Hosting**: gives you a free `*.web.app` domain + HTTPS and proxies to Cloud Run

> You must enable billing for Cloud Run in most cases. Many personal demos stay within free tier, but it depends on traffic.

## Prereqs (one-time on your machine)

Install:

- Google Cloud SDK (`gcloud`)
- Firebase CLI (`firebase-tools`)
- Docker (needed to build/push container images)

Then log in:

```bash
gcloud auth login
gcloud auth application-default login
firebase login
```

## 1) Create a new GCP project and link Firebase

Pick a project id (must be globally unique), like `vaultboard-12345`.

```bash
export PROJECT_ID="vaultboard-12345"
export REGION="us-central1"

gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"
```

Now open the Firebase console and add Firebase to this project:

- Firebase Console → Add project → select your GCP project id

Enable these APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 2) Deploy the container to Cloud Run

From repo root:

```bash
gcloud run deploy vaultboard \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated
```

Copy the Cloud Run URL it prints (looks like `https://vaultboard-xxxxx-uc.a.run.app`).

## 3) Configure Firebase Hosting rewrite → Cloud Run

This repo includes:

- `firebase.json` (rewrite to Cloud Run)
- `.firebaserc` (project mapping)

Edit `.firebaserc` and set your project id, or run:

```bash
firebase use --add "$PROJECT_ID"
```

Then initialize hosting (creates the hosting site if needed):

```bash
firebase init hosting
```

When prompted:
- **Use existing project** → choose your `$PROJECT_ID`
- **Public directory** → `public`
- **Configure as a single-page app** → **No**
- **Set up automatic builds/deploys with GitHub** → optional

Finally deploy hosting:

```bash
firebase deploy --only hosting
```

Your public URL will look like:

`https://<firebase-site>.web.app`

## Secrets / environment variables

If you use OpenAI/Plaid/Auth0, set env vars on Cloud Run:

```bash
gcloud run services update vaultboard \
  --region "$REGION" \
  --set-env-vars OPENAI_MODEL=gpt-4o-mini
```

For secrets (recommended), use Secret Manager and `--set-secrets`.

## Notes

- The app writes JSON files locally for snapshots/activity; Cloud Run filesystem is **ephemeral**.
  For persistence, move those JSON stores to a DB (Firestore/SQLite on volume/Cloud Storage/etc.).

