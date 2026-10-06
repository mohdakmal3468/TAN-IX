# ☁️ Google Cloud Setup Checklist for TAN-IX Capstone

Follow this checklist step-by-step in your terminal (PowerShell or Bash) to set up your Google Cloud environment.  
Replace **`YOUR_PROJECT_ID`** with your actual GCP project ID before running.

---

### Step 1: Login & Select Your Project

1. Authenticate with your Google account in the terminal:
   ```bash
   gcloud auth login
   ```
   *Logs into your Google account and authorizes the Google Cloud CLI.*

2. Set your active project ID:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```
   *Sets YOUR_PROJECT_ID as the default active project for all following commands.*

---

### Step 2: Enable All Required APIs

Run the following command to enable all 6 required services at once:

```bash
gcloud services enable firestore.googleapis.com bigquery.googleapis.com run.googleapis.com aiplatform.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```
*Enables Firestore, BigQuery, Cloud Run, Vertex AI, Artifact Registry, and Cloud Build APIs in one step.*

#### Individual API Breakdown (One-Line Explanations):
- `gcloud services enable firestore.googleapis.com`  
  *Enables Cloud Firestore NoSQL database for real-time warehouse inventory tracking.*
- `gcloud services enable bigquery.googleapis.com`  
  *Enables BigQuery data warehouse for analyzing historical shipment transit times and delays.*
- `gcloud services enable run.googleapis.com`  
  *Enables Cloud Run serverless engine to host and auto-scale your containerized application.*
- `gcloud services enable aiplatform.googleapis.com`  
  *Enables Vertex AI for Gemini reasoning models and vector search embeddings.*
- `gcloud services enable artifactregistry.googleapis.com`  
  *Enables Artifact Registry to securely store and version your Docker container images.*
- `gcloud services enable cloudbuild.googleapis.com`  
  *Enables Cloud Build to package your source code into Docker images in the cloud.*

---

### Step 3: Initialize Database & Analytics Services

1. Initialize your Firestore Database in the Mumbai region:
   ```bash
   gcloud firestore databases create --location=asia-south1 --type=firestore-native
   ```
   *Creates a native mode Firestore database in the Mumbai region for low-latency live stock updates.*

2. Create your BigQuery Dataset for logistics records:
   ```bash
   bq mk --location=asia-south1 --dataset YOUR_PROJECT_ID:up_leather_logistics
   ```
   *Creates the BigQuery dataset `up_leather_logistics` in the Mumbai region to store historical shipment logs.*

3. Create your Artifact Registry Docker repository:
   ```bash
   gcloud artifacts repositories create tan-ix-repo --repository-format=docker --location=asia-south1 --description="TAN-IX Docker Repository"
   ```
   *Creates a Docker repository named `tan-ix-repo` in the Mumbai region to store images for Cloud Run.*

---

### Step 4: Create a Service Account for Local Development

1. Create a dedicated service account:
   ```bash
   gcloud iam service-accounts create tan-ix-sa --display-name="TAN-IX Service Account"
   ```
   *Creates a secure identity for your Python app to connect to GCP services.*

2. Grant Firestore permissions:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:tan-ix-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" --role="roles/datastore.user"
   ```
   *Allows the service account to read and write live inventory documents in Firestore.*

3. Grant BigQuery permissions:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:tan-ix-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" --role="roles/bigquery.admin"
   ```
   *Allows the service account to run queries and insert logs in BigQuery.*

4. Generate a local credentials JSON key:
   ```bash
   gcloud iam service-accounts keys create credentials.json --iam-account=tan-ix-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```
   *Downloads a `credentials.json` key file to your project folder for local Python authentication.*

---

### Step 5: Set a Budget Alert (Prevent Accidental Charges)

1. Find your Billing Account ID:
   ```bash
   gcloud billing accounts list
   ```
   *Displays your active Google Cloud Billing Account ID (format: `XXXXXX-XXXXXX-XXXXXX`).*

2. Create a safety budget alert (e.g., ₹500 INR or $10 USD):
   ```bash
   gcloud billing budgets create --billing-account=YOUR_BILLING_ACCOUNT_ID --display-name="TAN-IX Capstone Budget" --budget-amount=500INR --threshold-rule=percent=0.5,basis=current-spend --threshold-rule=percent=0.9,basis=current-spend --threshold-rule=percent=1.0,basis=current-spend
   ```
   *Creates a budget alert that sends email notifications when your project reaches 50%, 90%, and 100% of ₹500.*

> **Console Alternative**: You can also set this in the browser at:  
> [Google Cloud Console Billing Budgets](https://console.cloud.google.com/billing/budgets) -> Click **Create Budget** -> Set amount to ₹500.

---

### Step 6: Verify Everything Is Ready

Run this single healthcheck command:
```bash
gcloud services list --enabled --filter="name:(firestore OR bigquery OR run OR aiplatform OR artifactregistry OR cloudbuild)"
```
*Lists all 6 enabled APIs to confirm your GCP capstone environment is fully configured.*
