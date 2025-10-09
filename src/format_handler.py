import re

FENCE_RE = re.compile(
  r'^\s*(```|~~~)\s*[a-zA-Z0-9+._-]*\s*\n(.*?)\n\s*\1\s*\s*$',
  re.DOTALL
)

def strip_code_fences(text: str) -> str:
  """
  If `text` is wrapped in Markdown code fences (``` or ~~~),
  return just the inner content; otherwise return text unchanged.
  """
  m = FENCE_RE.match(text)
  return m.group(2) if m else text