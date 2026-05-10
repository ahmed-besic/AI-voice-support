'use client';

import { useState } from 'react';

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

function toMultiline(items: string[]): string {
  return items.join('\n');
}

function fromMultiline(value: string): string[] {
  return value
    .split('\n')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export function AdminConsole({
  apiBaseUrl,
  initialSettings,
  initialSiteSummary,
  initialSessions,
  initialKnowledge,
}: {
  apiBaseUrl: string;
  initialSettings: SiteSettings | null;
  initialSiteSummary: SiteSummary | null;
  initialSessions: SessionRow[];
  initialKnowledge: KnowledgeEntry[];
}) {
  const [settings, setSettings] = useState<SiteSettings | null>(initialSettings);
  const [siteSummary, setSiteSummary] = useState<SiteSummary | null>(initialSiteSummary);
  const [sessions, setSessions] = useState<SessionRow[]>(initialSessions);
  const [knowledge, setKnowledge] = useState<KnowledgeEntry[]>(initialKnowledge);
  const [allowedOriginsText, setAllowedOriginsText] = useState(
    initialSettings ? toMultiline(initialSettings.allowedOrigins) : '',
  );
  const [supportedTopicsText, setSupportedTopicsText] = useState(
    initialSettings ? toMultiline(initialSettings.behavior.supportedTopics) : '',
  );
  const [forbiddenTopicsText, setForbiddenTopicsText] = useState(
    initialSettings ? toMultiline(initialSettings.behavior.forbiddenTopics) : '',
  );
  const [importText, setImportText] = useState('');
  const [knowledgeText, setKnowledgeText] = useState(
    JSON.stringify(
      {
        entries: initialKnowledge.map((entry) => ({
          title: entry.title,
          content: entry.content,
          source: entry.source,
          metadata: entry.metadata,
        })),
      },
      null,
      2,
    ),
  );
  const [saveState, setSaveState] = useState<string | null>(null);
  const [importState, setImportState] = useState<string | null>(null);
  const [knowledgeState, setKnowledgeState] = useState<string | null>(null);

  if (!settings) {
    return (
      <p className="empty-state">
        API not running yet. Start the backend to load and edit site settings.
      </p>
    );
  }

  const refreshMetrics = async () => {
    try {
      const [sitesResponse, sessionsResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/admin/sites`, { cache: 'no-store' }),
        fetch(`${apiBaseUrl}/admin/sites/${settings.siteId}/sessions`, { cache: 'no-store' }),
      ]);
      if (sitesResponse.ok) {
        const sites = (await sitesResponse.json()) as SiteSummary[];
        setSiteSummary(sites.find((entry) => entry.site_id === settings.siteId) ?? null);
      }
      if (sessionsResponse.ok) {
        setSessions((await sessionsResponse.json()) as SessionRow[]);
      }
      return true;
    } catch {
      return false;
    }
  };

  const saveSettings = async () => {
    try {
      setSaveState('Saving...');
      const payload = {
        displayName: settings.displayName,
        allowedOrigins: fromMultiline(allowedOriginsText),
        widget: settings.widget,
        models: settings.models,
        limits: settings.limits,
        behavior: {
          ...settings.behavior,
          supportedTopics: fromMultiline(supportedTopicsText),
          forbiddenTopics: fromMultiline(forbiddenTopicsText),
        },
        adapters: settings.adapters,
      };
      const response = await fetch(`${apiBaseUrl}/admin/site/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setSaveState(`Save failed (${response.status})`);
        return;
      }
      const nextSettings = (await response.json()) as SiteSettings;
      setSettings(nextSettings);
      setAllowedOriginsText(toMultiline(nextSettings.allowedOrigins));
      setSupportedTopicsText(toMultiline(nextSettings.behavior.supportedTopics));
      setForbiddenTopicsText(toMultiline(nextSettings.behavior.forbiddenTopics));
      const metricsRefreshed = await refreshMetrics();
      setSaveState(
        metricsRefreshed
          ? 'Saved. New sessions will use these settings.'
          : 'Saved. New sessions will use these settings, but metrics could not be refreshed.',
      );
    } catch {
      setSaveState('Save failed because the API could not be reached from the browser.');
    }
  };

  const exportSettings = async () => {
    try {
      setImportState('Loading export...');
      const response = await fetch(`${apiBaseUrl}/admin/site/settings/export`, {
        cache: 'no-store',
      });
      if (!response.ok) {
        setImportState(`Export failed (${response.status})`);
        return;
      }
      const payload = await response.json();
      setImportText(JSON.stringify(payload, null, 2));
      setImportState('Export loaded into the JSON editor below.');
    } catch {
      setImportState('Export failed because the API could not be reached from the browser.');
    }
  };

  const importSettings = async () => {
    setImportState('Importing...');
    let payload: unknown;
    try {
      payload = JSON.parse(importText);
    } catch {
      setImportState('Import failed: invalid JSON.');
      return;
    }
    try {
      const response = await fetch(`${apiBaseUrl}/admin/site/settings/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setImportState(`Import failed (${response.status})`);
        return;
      }
      const nextSettings = (await response.json()) as SiteSettings;
      setSettings(nextSettings);
      setAllowedOriginsText(toMultiline(nextSettings.allowedOrigins));
      setSupportedTopicsText(toMultiline(nextSettings.behavior.supportedTopics));
      setForbiddenTopicsText(toMultiline(nextSettings.behavior.forbiddenTopics));
      const metricsRefreshed = await refreshMetrics();
      setImportState(
        metricsRefreshed
          ? 'Imported. New sessions will use these settings.'
          : 'Imported. New sessions will use these settings, but metrics could not be refreshed.',
      );
    } catch {
      setImportState('Import failed because the API could not be reached from the browser.');
    }
  };

  const replaceKnowledge = async () => {
    setKnowledgeState('Importing knowledge...');
    let payload: unknown;
    try {
      payload = JSON.parse(knowledgeText);
    } catch {
      setKnowledgeState('Knowledge import failed: invalid JSON.');
      return;
    }
    try {
      const response = await fetch(`${apiBaseUrl}/admin/sites/${settings.siteId}/knowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setKnowledgeState(`Knowledge import failed (${response.status})`);
        return;
      }
      const nextKnowledge = (await response.json()) as KnowledgeEntry[];
      setKnowledge(nextKnowledge);
      setKnowledgeText(
        JSON.stringify(
          {
            entries: nextKnowledge.map((entry) => ({
              title: entry.title,
              content: entry.content,
              source: entry.source,
              metadata: entry.metadata,
            })),
          },
          null,
          2,
        ),
      );
      setKnowledgeState('Knowledge replaced for future sessions.');
    } catch {
      setKnowledgeState('Knowledge import failed because the API could not be reached from the browser.');
    }
  };

  return (
    <>
      <section className="admin-header">
        <span className="hero-label">Self-hosted config console</span>
        <h1>Configure the embedded support widget from one backend-owned source of truth.</h1>
        <p>
          These admin endpoints are unauthenticated in v1 and are intended for trusted self-hosted
          environments only. Do not expose the API publicly without network restrictions or real
          auth in front of it.
        </p>
      </section>

      <section className={`callout ${settings.apiKeyStatus.configured ? 'ok' : 'warn'}`}>
        <strong>{settings.apiKeyStatus.configured ? 'API key configured' : 'API key missing'}</strong>
        <p>{settings.apiKeyStatus.message}</p>
      </section>

      <section className="settings-grid">
        <div className="settings-card">
          <h2>Basics</h2>
          <label>
            <span>Display name</span>
            <input
              value={settings.displayName}
              onChange={(event) =>
                setSettings({ ...settings, displayName: event.target.value })
              }
            />
          </label>
          <label>
            <span>Allowed origins</span>
            <textarea
              rows={4}
              value={allowedOriginsText}
              onChange={(event) => setAllowedOriginsText(event.target.value)}
            />
          </label>
        </div>

        <div className="settings-card">
          <h2>Widget</h2>
          <label>
            <span>Title</span>
            <input
              value={settings.widget.title}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  widget: { ...settings.widget, title: event.target.value },
                })
              }
            />
          </label>
          <label>
            <span>Welcome message</span>
            <textarea
              rows={3}
              value={settings.widget.welcomeMessage}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  widget: { ...settings.widget, welcomeMessage: event.target.value },
                })
              }
            />
          </label>
          <div className="inline-fields">
            <label>
              <span>Theme</span>
              <select
                value={settings.widget.theme}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      theme: event.target.value as SiteSettings['widget']['theme'],
                    },
                  })
                }
              >
                <option value="graphite">graphite</option>
                <option value="sand">sand</option>
                <option value="ocean">ocean</option>
              </select>
            </label>
            <label>
              <span>Default mode</span>
              <select
                value={settings.widget.defaultMode}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      defaultMode: event.target.value as 'voice' | 'text',
                    },
                  })
                }
              >
                <option value="voice">voice</option>
                <option value="text">text</option>
              </select>
            </label>
          </div>
          <div className="checkbox-row">
            <label>
              <input
                type="checkbox"
                checked={settings.widget.voiceEnabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: { ...settings.widget, voiceEnabled: event.target.checked },
                  })
                }
              />
              <span>Voice enabled</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={settings.widget.textEnabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: { ...settings.widget, textEnabled: event.target.checked },
                  })
                }
              />
              <span>Text enabled</span>
            </label>
          </div>
          <div className="inline-fields">
            <label>
              <span>Countdown warning</span>
              <input
                type="number"
                value={settings.widget.countdownWarningSeconds}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      countdownWarningSeconds: Number(event.target.value),
                    },
                  })
                }
              />
            </label>
            <label>
              <span>VAD disabled</span>
              <input
                type="checkbox"
                checked={settings.widget.vadConfig.disabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      vadConfig: {
                        ...settings.widget.vadConfig,
                        disabled: event.target.checked,
                      },
                    },
                  })
                }
              />
            </label>
          </div>
          <div className="inline-fields">
            <label>
              <span>Speech start</span>
              <select
                value={settings.widget.vadConfig.startOfSpeechSensitivity}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      vadConfig: {
                        ...settings.widget.vadConfig,
                        startOfSpeechSensitivity: event.target.value as SiteSettings['widget']['vadConfig']['startOfSpeechSensitivity'],
                      },
                    },
                  })
                }
              >
                <option value="START_SENSITIVITY_LOW">low</option>
                <option value="START_SENSITIVITY_HIGH">high</option>
              </select>
            </label>
            <label>
              <span>Speech end</span>
              <select
                value={settings.widget.vadConfig.endOfSpeechSensitivity}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      vadConfig: {
                        ...settings.widget.vadConfig,
                        endOfSpeechSensitivity: event.target.value as SiteSettings['widget']['vadConfig']['endOfSpeechSensitivity'],
                      },
                    },
                  })
                }
              >
                <option value="END_SENSITIVITY_LOW">low</option>
                <option value="END_SENSITIVITY_HIGH">high</option>
              </select>
            </label>
          </div>
          <div className="inline-fields">
            <label>
              <span>Prefix padding (ms)</span>
              <input
                type="number"
                value={settings.widget.vadConfig.prefixPaddingMs}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      vadConfig: {
                        ...settings.widget.vadConfig,
                        prefixPaddingMs: Number(event.target.value),
                      },
                    },
                  })
                }
              />
            </label>
            <label>
              <span>Silence duration (ms)</span>
              <input
                type="number"
                value={settings.widget.vadConfig.silenceDurationMs}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    widget: {
                      ...settings.widget,
                      vadConfig: {
                        ...settings.widget.vadConfig,
                        silenceDurationMs: Number(event.target.value),
                      },
                    },
                  })
                }
              />
            </label>
          </div>
        </div>

        <div className="settings-card">
          <h2>Prompt behavior</h2>
          <label className="checkbox-single">
            <input
              type="checkbox"
              checked={settings.behavior.strictBehaviorEnabled}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  behavior: {
                    ...settings.behavior,
                    strictBehaviorEnabled: event.target.checked,
                  },
                })
              }
            />
            <span>Strict behavior enforcement enabled</span>
          </label>
          <label>
            <span>Supported topics</span>
            <textarea
              rows={5}
              value={supportedTopicsText}
              onChange={(event) => setSupportedTopicsText(event.target.value)}
            />
          </label>
          <label>
            <span>Forbidden topics</span>
            <textarea
              rows={5}
              value={forbiddenTopicsText}
              onChange={(event) => setForbiddenTopicsText(event.target.value)}
            />
          </label>
          <label>
            <span>Refusal tone</span>
            <select
              value={settings.behavior.refusalTone}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  behavior: {
                    ...settings.behavior,
                    refusalTone: event.target.value as SiteSettings['behavior']['refusalTone'],
                  },
                })
              }
            >
              <option value="polite">polite</option>
              <option value="firm">firm</option>
              <option value="brief">brief</option>
            </select>
          </label>
          <label>
            <span>Custom instructions</span>
            <textarea
              rows={6}
              value={settings.behavior.customInstructions}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  behavior: {
                    ...settings.behavior,
                    customInstructions: event.target.value,
                  },
                })
              }
            />
          </label>
        </div>

        <div className="settings-card">
          <h2>Models and limits</h2>
          <label>
            <span>Realtime model</span>
            <input
              value={settings.models.realtimeModel}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  models: { ...settings.models, realtimeModel: event.target.value },
                })
              }
            />
          </label>
          <label>
            <span>Text fallback model</span>
            <input
              value={settings.models.textFallbackModel}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  models: { ...settings.models, textFallbackModel: event.target.value },
                })
              }
            />
          </label>
          <label>
            <span>Summary model</span>
            <input
              value={settings.models.summaryModel}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  models: { ...settings.models, summaryModel: event.target.value },
                })
              }
            />
          </label>
          <div className="inline-fields">
            <label>
              <span>Max session seconds</span>
              <input
                type="number"
                value={settings.limits.maxSessionDurationSeconds}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    limits: {
                      ...settings.limits,
                      maxSessionDurationSeconds: Number(event.target.value),
                    },
                  })
                }
              />
            </label>
            <label>
              <span>Concurrent sessions</span>
              <input
                type="number"
                value={settings.limits.maxConcurrentSessions}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    limits: {
                      ...settings.limits,
                      maxConcurrentSessions: Number(event.target.value),
                    },
                  })
                }
              />
            </label>
          </div>
          <div className="inline-fields">
            <label>
              <span>Daily session limit</span>
              <input
                type="number"
                value={settings.limits.dailySessionLimit}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    limits: {
                      ...settings.limits,
                      dailySessionLimit: Number(event.target.value),
                    },
                  })
                }
              />
            </label>
            <label>
              <span>Monthly budget</span>
              <input
                type="number"
                step="0.01"
                value={settings.limits.monthlyUsageBudget}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    limits: {
                      ...settings.limits,
                      monthlyUsageBudget: Number(event.target.value),
                    },
                  })
                }
              />
            </label>
          </div>
        </div>

        <div className="settings-card">
          <h2>Adapters</h2>
          <div className="checkbox-row stacked">
            {['faq_search', 'create_support_ticket'].map((adapterName) => {
              const enabled = settings.adapters.enabledAdapters.includes(adapterName);
              return (
                <label key={adapterName}>
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(event) => {
                      const nextAdapters = event.target.checked
                        ? [...settings.adapters.enabledAdapters, adapterName]
                        : settings.adapters.enabledAdapters.filter((entry) => entry !== adapterName);
                      setSettings({
                        ...settings,
                        adapters: { enabledAdapters: nextAdapters },
                      });
                    }}
                  />
                  <span>{adapterName}</span>
                </label>
              );
            })}
          </div>
          <p className="helper-text">
            File edits require a backend restart or an explicit import. Settings saved here apply
            immediately to new sessions.
          </p>
        </div>
      </section>

      <section className="actions-row">
        <button className="cta" type="button" onClick={saveSettings}>
          Save settings
        </button>
        <span className="helper-text">{saveState}</span>
      </section>

      <section className="settings-card full-width">
        <h2>Config import and export</h2>
        <p className="helper-text">
          Export the current backend config, edit it manually, then import it back without storing
          any secrets in the file.
        </p>
        <div className="actions-row">
          <button className="cta" type="button" onClick={exportSettings}>
            Load export JSON
          </button>
          <button className="cta" type="button" onClick={importSettings}>
            Import JSON
          </button>
          <span className="helper-text">{importState}</span>
        </div>
        <textarea
          className="json-editor"
          rows={16}
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
        />
      </section>

      <section className="settings-card full-width">
        <h2>Knowledge</h2>
        <p className="helper-text">
          Replace the site knowledge store with JSON in the same shape used by the backend
          knowledge API.
        </p>
        <div className="actions-row">
          <button className="cta" type="button" onClick={replaceKnowledge}>
            Replace knowledge
          </button>
          <span className="helper-text">{knowledgeState}</span>
        </div>
        <textarea
          className="json-editor"
          rows={14}
          value={knowledgeText}
          onChange={(event) => setKnowledgeText(event.target.value)}
        />
        <div className="knowledge-list">
          {knowledge.map((entry) => (
            <article key={entry.id} className="knowledge-item">
              <strong>{entry.title}</strong>
              <p>{entry.content}</p>
              {entry.source ? <span>{entry.source}</span> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="stats-grid">
        <div className="metric-card">
          <span>Active sessions</span>
          <strong>{siteSummary?.active_sessions ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Today</span>
          <strong>{siteSummary?.daily_sessions ?? 0}</strong>
        </div>
        <div className="metric-card">
          <span>Cost / budget</span>
          <strong>
            ${(siteSummary?.monthly_estimated_cost ?? 0).toFixed(2)} / $
            {(siteSummary?.monthly_budget ?? settings.limits.monthlyUsageBudget).toFixed(2)}
          </strong>
        </div>
      </section>

      <section>
        <h2 className="section-kicker">Recent sessions</h2>
        {sessions.length > 0 ? (
          <>
            <div className="session-header">
              <span>Time</span>
              <span>Mode</span>
              <span>Status</span>
              <span>Cost</span>
            </div>
            <ul className="session-list">
              {sessions.map((session) => (
                <li key={session.id} className="session-item">
                  <span>{new Date(session.created_at).toLocaleString()}</span>
                  <span>{session.mode}</span>
                  <span>{session.status}</span>
                  <span>${session.estimated_cost.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="empty-state">No sessions captured yet.</p>
        )}
      </section>
    </>
  );
}
