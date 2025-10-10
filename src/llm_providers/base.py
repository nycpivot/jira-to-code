from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class ProviderConfig:
  """Generic configuration for any LLM provider."""
  model: Optional[str] = None
  api_key: Optional[str] = None
  base_url: Optional[str] = None

@dataclass
class Generation:
  """Represents a single response from the LLM."""
  llm: str
  text: str
  raw: Optional[Any] = None

class LLMProvider(ABC):
  """Abstract base class defining a common LLM interface."""
  def __init__(self, config: ProviderConfig):
    self.config = config

  @abstractmethod
  def generate(self, messages, request_timeout: int = 500, **params) -> Generation:
    """Perform a single text generation call."""
    pass
