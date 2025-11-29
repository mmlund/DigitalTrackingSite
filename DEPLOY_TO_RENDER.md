# Deploying to Render

This guide explains how to deploy your application to Render using the newly created `render.yaml` file.

## Prerequisites

1.  A [Render](https://render.com/) account.
2.  Your code pushed to GitHub (which we just did!).

## Steps to Deploy

1.  **Log in to Render** and go to your Dashboard.
2.  Click **New +** and select **Blueprint**.
3.  Connect your GitHub account if you haven't already.
4.  Select the **DigitalTrackingSite** repository.
5.  Render will automatically detect the `render.yaml` file.
6.  **Environment Variables**:
    *   Render will ask you to provide values for environment variables marked as `sync: false` in the YAML.
    *   **MONGO_URI**: Enter your actual MongoDB connection string here (the one from your `.env` file).
    *   **SECRET_KEY**: Render will generate a secure one for you automatically.
7.  Click **Apply**.

## Enabling Auto-Domain Detection (Subdomains)

To separate data by subdomain (e.g., `client1.dnstrainer.com`, `client2.dnstrainer.com`):

1.  After deployment, go to your **Service Settings** in Render.
2.  Find the **Custom Domains** section.
3.  Add a **Wildcard Domain**: `*.yourdomain.com` (e.g., `*.dnstrainer.com`).
4.  Configure your DNS provider (GoDaddy, Namecheap, etc.) to point `*` (CNAME or A record) to your Render app.
5.  **That's it!** The application is now updated to automatically detect and store:
    *   `host`: The full hostname (e.g., `client1.dnstrainer.com`)
    *   `subdomain`: The first part (e.g., `client1`)
    *   `domain`: The root domain (e.g., `dnstrainer.com`)

You can then filter your data in MongoDB using the `subdomain` field.

## What `render.yaml` Does

*   **Type**: Web Service
*   **Runtime**: Python
*   **Build Command**: `pip install -r requirements.txt` (Installs dependencies)
*   **Start Command**: `gunicorn app:app` (Runs the production server)
*   **Environment**: Sets Python version and Flask environment.

## Troubleshooting

*   **Build Failed**: Check the logs. Usually, this means a dependency is missing from `requirements.txt`.
*   **Deploy Failed**: Check the logs. Often this is due to a missing or incorrect `MONGO_URI`.
