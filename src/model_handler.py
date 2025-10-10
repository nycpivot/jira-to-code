import logging, os, json, requests

from format_handler import strip_code_fences
from format_handler import normalize_json
from format_handler import normalize_pdfs
from format_handler import payload_to_chunks
from format_handler import chunks_to_blocks

from llm_providers.base import LLMProvider
from llm_providers.llm_factory import get_provider

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


def process_payload(work_item_details):
  system_prompt = get_system_prompt()

  payloads = normalize_json(work_item_details.get("payloads"))
  chunks = payload_to_chunks(payloads)

  user_prompt = """
    IMPORTANT: Return a brief summary as Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, no other text. There is a max
    limit imposed by Jira of 30K bytes. There is no reason for a lengthy response.\n\n
    The title or heading of the summary should be called 'Payload Form Analysis'.
    Make sure to highlight any anomolies or discrepancies in the payload.\n\n
    Make use of tables, charts, graphs, and emojis for effect.
  """

  full_prompt = chunks_to_blocks(chunks, user_prompt)

  messages = [{"role": "user", "content": full_prompt}]

  provider = get_provider()
  response = provider.generate(
    messages, timeout=60, temperature=0.2, max_tokens=50000)

  # append Claude's reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  messages.append({"role": "assistant", "content": assistant_message})

  return response, messages


def process_jira_requirements(work_item_details, messages):
  print("=== Sending Jira summary and description ===")
  print(work_item_details.get("summary"))
  print(work_item_details.get("description"))

  system_prompt = get_system_prompt()

  payloads = normalize_pdfs(work_item_details.get("payloads"))
  chunks = payload_to_chunks(payloads)

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
    
    Make use of tables, charts, graphs, and emojis for effect.\n\n

    The title or heading of the summary should be called 'Task requirements analysis'.

    IMPORTANT: Return your response as Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, no other text.
  """

  messages.append({"role": "user", "content": user_prompt})

  provider = get_provider()

  # GPT needs a higher timeout :/
  response = provider.generate(
    messages, timeout=900, temperature=0.2, max_tokens=10000)

  # append Claude's reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  messages.append({"role": "assistant", "content": assistant_message})

  return response, messages


def build_code(work_item_details, messages):
  system_prompt = get_system_prompt()

  user_prompt = """
    You will generate the rules and logic based on the payload, 
    the summary and description recorded by the business analyst in the 
    Jira work item, as well as any additional rules and validations
    defined by official IRS documents, and code these rules into a 
    single Java Spring Boot class with JsonNode from jackson package. 
    No project, no unit tests.\n\n

    Return ONLY valid JSON with:
    {{"project":"tax-dvs","files":[{{"path":"pom.xml","content_b64":"..."}}]}}
  """

  messages.append({"role": "user", "content": user_prompt})

  provider = get_provider()
  response = provider.generate(
    messages, timeout=600, temperature=0.2, max_tokens=50000)

  return response, messages

