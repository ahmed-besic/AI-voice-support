'use client';

import { useEffect } from 'react';
import { initVoiceSupportWidget } from '@voice-support/widget';

export function WidgetHost() {
  useEffect(() => {
    const teardown = initVoiceSupportWidget({
      apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
      siteId: process.env.NEXT_PUBLIC_SITE_ID ?? 'demo-site',
      mount: document.body,
      title: 'Support voicebot',
      welcomeMessage: 'Ask for product help, ticket updates, or documentation guidance.',
    });
    return () => teardown.destroy();
  }, []);

  return null;
}
