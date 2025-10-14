import requests

from llm_providers.base import LLMProvider, ProviderConfig, Generation

class GptProvider(LLMProvider):
  def __init__(self, config):
    super().__init__(config)

  def _endpoint(self) -> str:
    base = self.config.base_url or "https://api.openai.com/v1"
    return f"{base.rstrip('/')}/chat/completions"

  def _headers(self) -> dict:
    return {
      "Authorization": f"Bearer {self.config.api_key}",
      "Content-Type": "application/json"
    }

  def append_user_message(self, message):
    self.messages.append({"role": "user", "content": message})

  def append_assistant_message(self, message):
    self.messages.append({"role": "assistant", "content": message})

  def generate(self, request_timeout: int = 500, **params) -> Generation:
    payload = {"model": self.config.model, "messages": self.messages}

    # ALLOWED = {
    #   "top_p","max_output_tokens","n","stop",
    #   "presence_penalty","frequency_penalty","logit_bias",
    #   "tool_choice","tools","response_format","seed","user"
    # }

    # payload.update({k: v for k, v in params.items() if k in ALLOWED})

    if "max_tokens" in params:
      payload["max_completion_tokens"] = int(params["max_tokens"])

    # print(f"MESSAGE: {self.messages[-1]}")

    resp = requests.post(self._endpoint(), headers=self._headers(),
                          json=payload, timeout=request_timeout)
    try:
      resp.raise_for_status()
    except requests.HTTPError:
      # print server message to see the exact reason
      raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text}") from None

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    model = self.config.model

    return Generation(llm=model, text=text, raw=data)
