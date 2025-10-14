import os

from typing import Optional

from llm_providers.base import LLMProvider
from llm_providers.base import ProviderConfig

_provider_singleton: Optional[LLMProvider] = None

def get_provider() -> LLMProvider:
  """
  Convenience: picks provider by model and pulls API keys from env.
  - For GPT: OPENAI_API_KEY, optional OPENAI_BASE_URL
  - For Claude: ANTHROPIC_API_KEY, optional ANTHROPIC_BASE_URL
  """
  global _provider_singleton
  if _provider_singleton is None:
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
    if model.lower().startswith(("gpt", "o3", "o4")):
      from llm_providers.gpt_provider import GptProvider
      cfg = ProviderConfig(
        model=model,
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY")
      )
      _provider_singleton = GptProvider(cfg)

    if model.lower().startswith("claude"):
      from llm_providers.claude_provider import ClaudeProvider
      cfg = ProviderConfig(
        model=model,
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        api_key=os.environ.get("ANTHROPIC_API_KEY")
      )
      _provider_singleton = ClaudeProvider(cfg)

    if model.lower().startswith("grok"):
      from llm_providers.grok_provider import GrokProvider
      cfg = ProviderConfig(
        model=model,
        base_url=os.environ.get("XAI_BASE_URL"),
        api_key=os.environ.get("XAI_API_KEY")
      )
      _provider_singleton = GrokProvider(cfg)

    if model.lower().startswith("qwen"):
      from llm_providers.qwen_provider import QwenProvider
      cfg = ProviderConfig(
        model=model,
        base_url=os.environ.get("HF_BASE_URL"),
        api_key=os.environ.get("HF_API_KEY")
      )
      _provider_singleton = QwenProvider(cfg)

    # raise ValueError(f"Cannot infer provider from model '{model}'.")

  return _provider_singleton


def get_image_provider(model: str) -> LLMProvider:
  # files = {
  #   "image": base_img,
  #   "mask": mask_img,
  # }
  data = {
      "model": "gpt-image-1",
      "prompt": "Replace the legend with a compact one in the top-right",
      "size": "1024x1024",
      "response_format": "b64_json",
  }

  cfg = ProviderConfig(
    model=model,
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
  )
  _provider_singleton = GptProvider(cfg)

