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

## What `render.yaml` Does

*   **Type**: Web Service
*   **Runtime**: Python
*   **Build Command**: `pip install -r requirements.txt` (Installs dependencies)
*   **Start Command**: `gunicorn app:app` (Runs the production server)
*   **Environment**: Sets Python version and Flask environment.

## Troubleshooting

*   **Build Failed**: Check the logs. Usually, this means a dependency is missing from `requirements.txt`.
*   **Deploy Failed**: Check the logs. Often this is due to a missing or incorrect `MONGO_URI`.
