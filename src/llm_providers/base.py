from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, List

@dataclass
class ProviderConfig:
  # generic configuration for any LLM provider
  model: Optional[str] = None
  api_key: Optional[str] = None
  base_url: Optional[str] = None

@dataclass
class Generation:
  # represents a single response from the LLM
  llm: str
  text: str
  raw: Optional[Any] = None

class LLMProvider(ABC):
  def __init__(self, config: ProviderConfig):
    self.config = config
    self.system_message = None
    self.messages: List[Any] = []

  @abstractmethod
  def append_system_message(self, message):
    pass

  @abstractmethod
  def append_user_message(self, message):
    pass

  @abstractmethod
  def append_assistant_message(self, message):
    pass

  @abstractmethod
  def generate(self, request_timeout: int = 500, **params) -> Generation:
    pass
