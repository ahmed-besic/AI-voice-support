# Adapter Authoring

Adapters let integrators connect the widget to their own systems without editing core runtime code.

## Tool adapter contract
Implement a class that exposes:
- `spec.name`
- `spec.description`
- `spec.schema`
- `execute(args, session_id, site_id)`

Reference examples live in:
- `services/api/app/adapters/faq.py`
- `services/api/app/adapters/tickets.py`

## Registration
Add the adapter to `services/api/app/adapters/registry.py` and enable its name in the site configuration.

## Security expectations
- Validate and normalize all external inputs.
- Keep side effects explicit and easy to audit.
- Return structured outputs that the model can safely speak back to users.
- Avoid embedding secrets in adapter source; read them from backend config instead.

## Recommended pattern
1. Keep knowledge retrieval adapters read-only.
2. Keep mutating adapters narrow and idempotent when possible.
3. Log every tool call through the existing `tool_events` path.
4. Add focused unit tests around the adapter's argument parsing and failure cases.

## Built-in knowledge path
The default `faq_search` adapter reads from the per-site `knowledge_entries` store. For many self-hosted installs, that means you can load company content through the admin knowledge API instead of writing a custom adapter immediately.
