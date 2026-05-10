import { AdminConsole } from "../../components/AdminConsole";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}${path}`,
      {
        cache: "no-store",
      },
    );
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

type SiteSettings = {
  siteId: string;
  displayName: string;
  allowedOrigins: string[];
  widget: {
    title: string;
    welcomeMessage: string;
    defaultMode: 'voice' | 'text';
    voiceEnabled: boolean;
    textEnabled: boolean;
    theme: 'graphite' | 'sand' | 'ocean';
    countdownWarningSeconds: number;
    vadConfig: {
      disabled: boolean;
      startOfSpeechSensitivity: 'START_SENSITIVITY_LOW' | 'START_SENSITIVITY_HIGH';
      endOfSpeechSensitivity: 'END_SENSITIVITY_LOW' | 'END_SENSITIVITY_HIGH';
      prefixPaddingMs: number;
      silenceDurationMs: number;
    };
  };
  models: {
    realtimeModel: string;
    textFallbackModel: string;
    summaryModel: string;
  };
  limits: {
    maxSessionDurationSeconds: number;
    maxConcurrentSessions: number;
    dailySessionLimit: number;
    monthlyUsageBudget: number;
  };
  behavior: {
    strictBehaviorEnabled: boolean;
    supportedTopics: string[];
    forbiddenTopics: string[];
    refusalTone: 'polite' | 'firm' | 'brief';
    customInstructions: string;
  };
  adapters: {
    enabledAdapters: string[];
  };
  apiKeyStatus: {
    configured: boolean;
    message: string;
  };
};

type SiteSummary = {
  site_id: string;
  display_name: string;
  active_sessions: number;
  daily_sessions: number;
  monthly_estimated_cost: number;
  monthly_budget: number;
};

type SessionRow = {
  id: string;
  status: string;
  mode: string;
  estimated_cost: number;
  created_at: string;
};

type KnowledgeEntry = {
  id: string;
  title: string;
  content: string;
  source: string | null;
  metadata: Record<string, string>;
  created_at: string;
};

export default async function AdminPage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const siteId = process.env.NEXT_PUBLIC_SITE_ID ?? "demo-site";
  const settings = await fetchJson<SiteSettings>("/admin/site/settings");
  const sites = await fetchJson<SiteSummary[]>("/admin/sites");
  const sessions = await fetchJson<SessionRow[]>(`/admin/sites/${siteId}/sessions`);
  const knowledge = await fetchJson<KnowledgeEntry[]>(`/admin/sites/${siteId}/knowledge`);

  return (
    <main>
      <AdminConsole
        apiBaseUrl={apiBaseUrl}
        initialSettings={settings}
        initialSiteSummary={sites?.find((site) => site.site_id === siteId) ?? null}
        initialSessions={sessions ?? []}
        initialKnowledge={knowledge ?? []}
      />
    </main>
  );
}
