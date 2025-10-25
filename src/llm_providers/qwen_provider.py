import requests

from llm_providers.base import LLMProvider, ProviderConfig, Generation
  
class QwenProvider(LLMProvider):
  def __init__(self, config):
    super().__init__(config)

  def _endpoint(self) -> str:
    base = self.config.base_url or "https://a5f5v6wwyio1z8ox.us-east-1.aws.endpoints.huggingface.cloud"
    return f"{base.rstrip('/')}"

  def _headers(self) -> dict:
    return {
      "Authorization": f"Bearer {self.config.api_key}",
      "Content-Type": "application/json"
    }
  
  def append_system_message(self, message):
    self.messages.append({"role": "system", "content": message})

  def append_user_message(self, message):
    self.messages.append({"role": "user", "content": message})

  def append_assistant_message(self, message):
    self.messages.append({"role": "assistant", "content": message})

  def generate(self, request_timeout: int = 500, **params) -> Generation:
    prompt = format_messages_for_qwen(self.messages)

    temperature = float(params.get("temperature", 0.2))
    max_tokens  = int(params.get("max_tokens", 512))

    print(f"PROMPT: {prompt}")
    payload = {
      "inputs": prompt,
      "parameters": {
        "temperature": temperature,
        "max_new_tokens": max_tokens
      },
      "options": {
        "wait_for_model": True
      }
    }

    # payload = {
    #   "inputs": "Hello, how are you?",
    #   "parameters": {
    #       "max_new_tokens": 100
    #   },
    #   "options": {
    #       "wait_for_model": True
    #   }
    # }

    resp = requests.post(self._endpoint(), headers=self._headers(),
                          json=payload, timeout=request_timeout)

    # Parse and print the response
    if resp.status_code == 200:
      print(resp.json())
    else:
      print(f"Error: {resp.status_code}, {resp.text}")

    data = resp.json()

    print(F"QWEN DATA: {resp}")
    text = data[0]["generated_text"]
    model = self.config.model

    return Generation(llm=model, text=text, raw=data)


def format_messages_for_qwen(messages: list) -> str:
  """
  Convert chat messages to Qwen's expected format.
  Qwen uses special tokens for chat formatting.
  """
  formatted = ""
  
  for msg in messages:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    
    if role == "system":
      formatted += f"<|im_start|>system\n{content}<|im_end|>\n"
    elif role == "user":
      formatted += f"<|im_start|>user\n{content}<|im_end|>\n"
    elif role == "assistant":
      formatted += f"<|im_start|>assistant\n{content}<|im_end|>\n"
  
  # Add the assistant prompt to start generation
  formatted += "<|im_start|>assistant\n"
  
  return formatted