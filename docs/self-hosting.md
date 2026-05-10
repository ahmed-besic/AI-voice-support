# Self-Hosting Guide

## Requirements
- Node.js 25+
- Python 3.14+
- Docker for local Postgres
- A Google API key stored on the backend

## Important admin security note
- The v1 admin/settings endpoints are intentionally unauthenticated.
- They are for trusted local or private self-hosted deployments only.
- Do not expose port `8000` publicly unless you add real auth or restrict network access in front of the API.

## Boot sequence
1. Start Postgres with `docker compose up -d`.
2. Copy `services/api/.env.example` to `services/api/.env` and fill in:
   - `JWT_SECRET`
   - `FIELD_ENCRYPTION_KEY`
   - `DEFAULT_GOOGLE_API_KEY`
3. Copy `apps/demo/.env.local.example` to `apps/demo/.env.local`.
4. Install workspace deps with `npm install`.
5. Create the Python env and install backend deps.
6. Run `uvicorn app.main:app --reload --app-dir services/api`.
7. Run `npm run dev:demo`.

## Settings workflow
- The demo app now includes the default config console at `/admin`.
- Runtime settings are stored in the backend database.
- `services/api/config/site.json` is the seed/import-export format for OSS users who prefer file editing.
- Editing `site.json` requires a backend restart or importing the JSON through the admin console.
- Settings saved in the UI take effect immediately for new sessions.
- The UI shows only whether `DEFAULT_GOOGLE_API_KEY` is configured; the key value is never exposed.

## CSP and CORS
For a third-party website embed, allow:
- `connect-src` to your FastAPI backend
- `connect-src` to Gemini Live API endpoints
- `script-src` for wherever you host the widget bundle

The backend enforces:
- per-site allowed origins
- short-lived widget session JWTs
- Gemini ephemeral tokens for voice sessions
- session duration and spend checks before bootstrap

## Local demo site
The seeded demo site uses `demo-site` and defaults to `http://localhost:3000` as an allowed origin.

## Loading company knowledge
Each customer-facing site can have its own support knowledge inside the backend database.

- Seeded demo data is loaded automatically from `services/api/data/faq.json`.
- List current knowledge with `GET /admin/sites/{site_id}/knowledge`.
- Replace a site's knowledge with `POST /admin/sites/{site_id}/knowledge`.

Example payload:

```json
{
  "entries": [
    {
      "title": "Refund policy",
      "content": "Refunds are processed within five business days.",
      "source": "help-center/refunds",
      "metadata": {
        "locale": "en"
      }
    },
    {
      "title": "Password reset",
      "content": "Customers can reset passwords from the sign-in page."
    }
  ]
}
```

The built-in `faq_search` adapter and text fallback path both read from this per-site knowledge store, so different embeds can serve different companies without changing core code.

## Strict behavior policy
The backend ships with a file-based policy at `services/api/policies/default.yaml`.

- Override the default behavior file with `STRICT_POLICY_OVERRIDE_PATH`.
- Edit `services/api/baml_src/*.baml` for deeper moderation logic changes.
- Re-generate the Python BAML client with `npm run generate:baml`.

Strict moderation-related endpoints:

- `POST /widget/sessions/{session_id}/turns` ingests final user turns for moderation.
- `GET /widget/sessions/{session_id}/control-stream` streams policy warnings, strikes, and termination events to the widget.
