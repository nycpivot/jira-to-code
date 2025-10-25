import requests

from llm_providers.base import LLMProvider, ProviderConfig, Generation

class ClaudeProvider(LLMProvider):
  def __init__(self, config):
    super().__init__(config)

  def _endpoint(self) -> str:
    base = self.config.base_url or "https://api.anthropic.com/v1"
    return f"{base.rstrip('/')}/messages"

  def _headers(self) -> dict:
    return {
      "x-api-key": self.config.api_key,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json"
    }
  
  def append_system_message(self, message):
    self.system_message = message

  def append_user_message(self, message):
    self.messages.append({"role": "user", "content": message})

  def append_assistant_message(self, message):
    self.messages.append({"role": "assistant", "content": message})

  def generate(self, request_timeout: int = 500, **params) -> Generation:
    payload = {"model": self.config.model, "system": self.system_message, "messages": self.messages}

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
      raise RuntimeError(f"LLM error {resp.status_code}: {resp.text}") from None

    data = resp.json()
    text = data["content"][0]["text"]
    model = self.config.model

    return Generation(llm=model, text=text, raw=data)
