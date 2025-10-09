import requests

from llm_providers.base import LLMProvider, ProviderConfig, Generation

class ClaudeProvider(LLMProvider):
  """Lightweight provider for OpenAI GPT models using raw HTTP requests."""

  def _endpoint(self) -> str:
    base = self.config.base_url or "https://api.anthropic.com/v1"
    return f"{base.rstrip('/')}/messages"

  def _headers(self) -> dict:
    return {
      "x-api-key": self.config.api_key,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json"
    }

  def generate(self, messages, request_timeout: int = 500, **params) -> Generation:
    payload = {"model": self.config.model, "messages": messages}

    ALLOWED = {
      "temperature","top_p","max_tokens","n","stop",
      "presence_penalty","frequency_penalty","logit_bias",
      "tool_choice","tools","response_format","seed","user"
    }
    payload.update({k: v for k, v in params.items() if k in ALLOWED})

    resp = requests.post(self._endpoint(), headers=self._headers(),
                          json=payload, timeout=request_timeout)
    try:
      resp.raise_for_status()
    except requests.HTTPError:
      # print server message to see the exact reason
      raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text}") from None

    data = resp.json()
    text = data["content"][0]["text"]
    return Generation(text=text, raw=data)
