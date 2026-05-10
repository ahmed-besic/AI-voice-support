enum ScopeDecision {
  IN_SCOPE
  OUT_OF_SCOPE
  AMBIGUOUS
}

class ScopeCheckResult {
  decision ScopeDecision
  reason_code string
  explanation string
}

function ScopeCheck(
  company_name: string,
  supported_topics: string[],
  forbidden_topics: string[],
  message: string
) -> ScopeCheckResult {
  client PolicyClient
  prompt #"
    You classify whether a user's message is inside or outside the customer support scope for {{ company_name }}.

    Supported topics:
    {% for topic in supported_topics %}
    - {{ topic }}
    {% endfor %}

    Explicitly out-of-scope topics:
    {% for topic in forbidden_topics %}
    - {{ topic }}
    {% endfor %}

    Classification rules:
    - Return IN_SCOPE only when the user is clearly asking for company support.
    - Return OUT_OF_SCOPE for trivia, unrelated general knowledge, unrelated chit-chat, competitor research, or other non-support requests.
    - Return AMBIGUOUS only when the message could plausibly be support-related but lacks enough context.
    - If the message is clearly unrelated, prefer OUT_OF_SCOPE instead of AMBIGUOUS.
    - reason_code must be short snake_case text.
    - explanation must be one concise sentence.

    User message:
    {{ message }}

    {{ ctx.output_format }}
  "#
}
