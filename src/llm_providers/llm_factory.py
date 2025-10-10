import os

from llm_providers.base import LLMProvider
from llm_providers.base import ProviderConfig

def get_provider() -> LLMProvider:
  """
  Convenience: picks provider by model and pulls API keys from env.
  - For GPT: OPENAI_API_KEY, optional OPENAI_BASE_URL
  - For Claude: ANTHROPIC_API_KEY, optional ANTHROPIC_BASE_URL
  """
  model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")

  if model.startswith(("gpt", "o3", "o4")):
    from llm_providers.gpt_provider import GptProvider
    cfg = ProviderConfig(
      model=model,
      api_key=os.environ.get("OPENAI_API_KEY"),
      base_url=os.environ.get("OPENAI_BASE_URL")
    )
    return GptProvider(cfg)

  if model.startswith("claude"):
    from llm_providers.claude_provider import ClaudeProvider
    cfg = ProviderConfig(
      model=model,
      api_key=os.environ.get("ANTHROPIC_API_KEY"),
      base_url=os.environ.get("ANTHROPIC_BASE_URL")
    )
    return ClaudeProvider(cfg)

  raise ValueError(f"Cannot infer provider from model '{model}'.")

