# Embedding the Support Widget

This guide shows how to add the voice support widget to your own site using the current open-source setup in this repository.

## What You Need

- A running backend from this repo
- A Google API key configured on the backend
- Your website origin added to the widget site's allowed origins
- The `@voice-support/widget` package installed in your frontend

## Backend Setup

Start from the self-hosting flow in [self-hosting.md](/Users/ahmedb/Documents/Fax/ideas_to_implement/AI voice support/docs/self-hosting.md).

Minimum backend requirements:

1. Run Postgres.
2. Copy `services/api/.env.example` to `services/api/.env`.
3. Set `DEFAULT_GOOGLE_API_KEY` in `services/api/.env`.
4. Start the API with `npm run dev:api` or your production FastAPI setup.

## Configure the Widget Site

Open the demo admin console at `/admin` on the demo app and configure:

- `Allowed origins`
- Theme
- Voice/text mode defaults
- System prompt behavior
- Limits and models
- Knowledge entries

Important:

- The origin must exactly match the host site where you embed the widget.
- Example local origin: `http://localhost:3000`
- Example production origin: `https://support.yourcompany.com`

If the origin is missing, widget bootstrap will be rejected by the backend.

## Install the Widget

In your frontend app:

```bash
npm install @voice-support/widget
```

## React / Next.js Example

Add a client component like this:

```tsx
'use client';

import { useEffect } from 'react';
import { initVoiceSupportWidget } from '@voice-support/widget';

export function SupportWidget() {
  useEffect(() => {
    const widget = initVoiceSupportWidget({
      apiBaseUrl: 'https://your-api.example.com',
      siteId: 'demo-site',
    });

    return () => widget.destroy();
  }, []);

  return null;
}
```

Render that component somewhere once, usually near the root layout or page shell.

## Plain Browser JavaScript Example

If you are not using React, initialize the widget from your own bundled JavaScript:

```js
import { initVoiceSupportWidget } from '@voice-support/widget';

const widget = initVoiceSupportWidget({
  apiBaseUrl: 'https://your-api.example.com',
  siteId: 'demo-site',
});
```

This repository does not yet ship a standalone copy-paste CDN embed script. The supported integration path today is npm/package-based embedding.

## Required Options

These are the only required init options:

- `apiBaseUrl`
- `siteId`

Example:

```ts
initVoiceSupportWidget({
  apiBaseUrl: 'https://your-api.example.com',
  siteId: 'demo-site',
});
```

## Optional Overrides

The widget reads its main presentation and behavior config from the backend on load.

You can still override these locally if needed:

- `title`
- `welcomeMessage`
- `theme`
- `mount`

Example:

```ts
initVoiceSupportWidget({
  apiBaseUrl: 'https://your-api.example.com',
  siteId: 'demo-site',
  title: 'Customer support',
  welcomeMessage: 'Ask us about billing, setup, or product issues.',
  theme: 'sand',
});
```

Use overrides only if you intentionally want host-side behavior to differ from the backend config.

## CSP Requirements

Your host site should allow network connections to:

- your FastAPI backend
- Gemini API endpoints used by the live session

At minimum, `connect-src` should allow:

- your backend origin
- `https://generativelanguage.googleapis.com`

Depending on your deployment, you may also need the Gemini Live websocket endpoint allowed by `connect-src`.

## What Happens at Runtime

When the widget loads:

1. It fetches public widget settings from the backend.
2. It applies theme, title, welcome message, and mode availability.
3. When the user starts voice or sends text, it bootstraps a session with the backend.
4. The backend validates the request origin before allowing the session.

## Troubleshooting

### The widget does not appear

Check:

- your component actually mounts in the page
- the frontend bundle includes `@voice-support/widget`
- the browser console for import or runtime errors

### Theme or welcome message does not update

Check:

- the settings were saved in `/admin`
- the page was reloaded after changing settings
- no local override is being passed to `initVoiceSupportWidget`

### Save works but the widget cannot connect

Check:

- `DEFAULT_GOOGLE_API_KEY` is set on the backend
- the admin console shows `API key configured`
- the host origin is listed in allowed origins

### Browser gets a 403 from `/widget/bootstrap`

Usually this means:

- the current page origin is not in allowed origins
- or the frontend is pointing at the wrong backend

### Voice fails and the widget falls back to text

That can happen when:

- microphone permission is denied
- the backend has no Google API key
- voice is disabled in site settings

## Current Integration Contract

Today this project is best for:

- self-hosted product sites
- React and Next.js apps
- teams comfortable installing a package and running the backend

It does not yet provide:

- a hosted SaaS control plane
- a one-line CDN embed snippet
- authenticated multi-tenant admin APIs

## Recommended Production Notes

- Keep admin APIs private unless you add auth in front of them.
- Do not expose the current unauthenticated admin endpoints publicly.
- Keep the Gemini API key only on the backend.
- Use the admin console for site config and knowledge updates.
