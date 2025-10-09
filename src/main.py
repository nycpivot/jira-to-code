import logging, boto3, json, os, base64

from jira_handler import load_jira
from jira_handler import add_comment

from model_handler import process_payload
from model_handler import process_jira_requirements

from format_handler import strip_code_fences

from llm_providers.base import ProviderConfig
from llm_providers.gpt_provider import GptProvider

# output to aws cloudwatch
log = logging.getLogger()
log.setLevel(logging.INFO)

def load_secrets():
  sm = boto3.client("secretsmanager")
  resp = sm.get_secret_value(SecretId="ai-jira-to-github-codegen-secrets")
  data = json.loads(resp["SecretString"])
  # make all keys available globally and as env vars
  os.environ.update(data)
  return data

SECRETS = load_secrets()

def main_handler(event, context):
  # API Gateway HTTP API (v2) headers
  headers = { (k or "").lower(): v for k, v in (event.get("headers") or {}).items() }

  # trim spaces and lowercase
  incoming = (headers.get("x-shared-jira-token") or "").strip().lower()
  expected = (os.environ["X_SHARED_JIRA_TOKEN"] or "").strip().lower()

  # authenticate caller is jira
  if expected and incoming != expected:
    return {"statusCode": 401, "body": "unauthorized"}

  # Get the raw body (handle potential base64)
  raw = event.get("body") or ""
  if event.get("isBase64Encoded"):
    raw = base64.b64decode(raw).decode("utf-8", errors="replace")

  # Try to parse JSON; if not JSON, just log as text
  try:
    work_item = json.loads(raw) if raw else {}
  except Exception:
    work_item = {"_raw": raw}

  # process jira payload
  work_item_details = load_jira(work_item)

  # Log everything so you can see it in CloudWatch
  log.info("=== Incoming headers ===")
  log.info(json.dumps(headers, ensure_ascii=False))
  log.info("=== Incoming body ===")
  log.info(json.dumps(work_item, ensure_ascii=False))


  config = ProviderConfig(
    model="claude-sonnet-4-5-20250929",
    api_key=os.environ["ANTHROPIC_API_KEY"]
  )

  # **************************************************************
  # send payload to llm for analysis
  # **************************************************************
  # 1) send first prompt to llm
  process_payload_response, messages = process_payload(config, work_item_details)

  log.info(f"COMMENT 1: {strip_code_fences(process_payload_response.text)}")

  # 2) add first observations of payload as a comment in jira
  add_comment(work_item, strip_code_fences(process_payload_response.text))
  # --------------------------------------------------------------


  # **************************************************************
  # send jira use case summary and description as followup instructions
  # **************************************************************
  # 1) send jira summary and description
  response_to_jira_reqs, messages = process_jira_requirements(config, work_item_details, messages)

  log.info(f"1: {messages[0]}")
  log.info(f"2: {messages[1]}")
  log.info(f"3: {messages[2]}")
  log.info(f"4: {messages[3]}")

  log.info(f"COMMENT 2: {strip_code_fences(response_to_jira_reqs.text)}")

  # 3) add llm response as another comment to jira
  add_comment(work_item, strip_code_fences(response_to_jira_reqs.text))
  # --------------------------------------------------------------


  # # **************************************************************
  # # generate code
  # # **************************************************************
  # # 1) prompt llm to generate project and code
  # data, messages = prompt_for_codegen(work_item_details, messages)

  # # 2) extract llm response
  # response_to_codegen = messages[-1]

  # code_path = pathlib.Path("/tmp/codegen")

  # # 3) source code is returns in a zip file as a decoded string
  # log.info(f"RESPONSE_TO_CODEGEN: {response_to_codegen}")
  # encoded_code = write_codegen(response_to_codegen, code_path)
  # log.info(f"ENCODED JAVA: {encoded_code}")

  # # # 4) add llm response as another comment to jira
  # # add_comment(work_item, "Java Spring Boot code generated at:", 
  # #             response_to_jira_details["content"][0]["text"])
  # # --------------------------------------------------------------