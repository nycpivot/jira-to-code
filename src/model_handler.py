import logging, os, json, requests

from format_handler import strip_code_fences

from llm_providers.base import ProviderConfig
from llm_providers.gpt_provider import GptProvider
from llm_providers.claude_provider import ClaudeProvider

# output to aws cloudwatch
log = logging.getLogger()
log.setLevel(logging.INFO)

def get_system_prompt():
  system_prompt = """
    You are a senior Java developer and application architect, 
    with expertise in examining IRS tax forms and the rules 
    governing the validity between forms.
  """

  return system_prompt


def process_payload(config, work_item_details):
  system_prompt = get_system_prompt()

  payloads = normalize_attachments(work_item_details.get("payloads"))
  chunks = payload_to_chunks(payloads, per_file_limit=4000, total_limit=20000)

  user_prompt = """
    IMPORTANT: Return a brief summary as Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, no other text. There is a max
    limit imposed by Jira of 30K bytes. There is no reason for a lengthy response.\n\n
    The title or heading of the summary should be called 'Payload Form Analysis'.
    Make sure to highlight any anomolies or discrepancies in the payload.\n\n
    Make use of tables, graphs, and emojis for effect.
  """
  
  full_prompt = [{"type": "text", "text": f"<attachment>\n{chunk}\n</attachment>"} for chunk in chunks]
  full_prompt.append({"type": "text", "text": user_prompt})

  messages = [{"role": "user", "content": full_prompt}]

  provider = ClaudeProvider(config)
  response = provider.generate(messages, timeout=60, temperature=0.2, max_tokens=10000)

  # append Claude's reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  messages.append({"role": "assistant", "content": assistant_message})

  return response, messages

def normalize_attachments(files):
  out = []
  for f in files or []:
    g = {k: v for k, v in f.items() if k != "bytes"}  # drop raw bytes
    b = f.get("bytes")
    name = (f.get("filename") or "").lower()
    mime = (f.get("mimeType") or "").lower()

    if not b:
      out.append(g); continue

    # texty types → decode; JSON → also parse
    if mime.startswith("application/json") or name.endswith(".json") or mime.startswith("text/"):
      txt = b.decode("utf-8", "replace")
      g["text"] = txt
      if mime.startswith("application/json") or name.endswith(".json"):
        try:
          g["json"] = json.loads(txt)
        except json.JSONDecodeError:
          pass
    else:
      # keep binary safely if you need it
      g["b64"] = base64.b64encode(b).decode("ascii")
      g["size"] = len(b)

    out.append(g)
  
  return out


def payload_to_chunks(data, per_file_limit=4000, total_limit=24000):
  """
  Accepts either:
    A) a list of parsed file dicts: [{filename, json, text, ...}]
    B) a merged list of raw JSON objects: [ {...}, {...} ]
  """
  chunks, total = [], 0

  # Detect case B (merged raw JSON list): it's a list of dicts/lists
  # and NOT our parsed file dicts (no 'json'/'text' keys).
  is_merged_raw = (
    isinstance(data, list)
    and data
    and all(isinstance(d, (dict, list)) for d in data)
    and not any(isinstance(d, dict) and ("json" in d or "text" in d) for d in data)
  )

  if is_merged_raw:
    s = json.dumps(data, ensure_ascii=False)
    for i in range(0, len(s), per_file_limit):
      chunk = s[i:i+per_file_limit]
      chunks.append(chunk)
      total += len(chunk)
      if total >= total_limit:
        break
    return chunks

  # Case A: list of parsed file dicts
  for p in (data or []):
    if p.get("json") is not None:
      s = json.dumps(p["json"], ensure_ascii=False)
    elif p.get("text"):
      s = p["text"]
    else:
      continue

    for i in range(0, len(s), per_file_limit):
      chunk = s[i:i+per_file_limit]
      chunks.append(chunk)
      total += len(chunk)
      if total >= total_limit:
        return chunks

  return chunks


def process_jira_requirements(config, work_item_details, messages):
  log.info("=== Sending Jira summary and description ===")
  log.info(work_item_details.get("summary"))
  log.info(work_item_details.get("description"))

  system_prompt = get_system_prompt()

  summary = work_item_details.get("summary")
  description = work_item_details.get("description")

  user_prompt = f"""
    In light of the JSON tax form payload, refine your initial analysis
    based on the following requirements defined by the jira ticket:\n\n

    Summary: {summary}\n
    Description: {description}\n\n

    These requirements must be applied to the IRS JSON tax form(s) you received, 
    and must also be examined in light of the offical IRS rules.\n\n

    Make sure to highlight any anomolies or discrepancies in the payload,
    specifically pertaining to the requirements defined in the summary and description.
    Make use of tables, graphs, and emojis for effect.\n\n
    
    Make use of tables, graphs, and emojis for effect.\n\n

    The title or heading of the summary should be called 'Task requirements analysis'.

    IMPORTANT: Return your response as Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, no other text.
  """

  messages.append({"role": "user", "content": user_prompt})

  provider = ClaudeProvider(config)
  response = provider.generate(messages, timeout=300, temperature=0.2, max_tokens=10000)

  # append Claude's reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  messages.append({"role": "assistant", "content": assistant_message})

  return response, messages
