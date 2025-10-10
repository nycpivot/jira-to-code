import logging, boto3, json, os, base64, pathlib

from jira_handler import load_jira
from jira_handler import add_comment

from model_handler import process_payload
from model_handler import process_jira_requirements
from model_handler import build_code

from format_handler import strip_code_fences
from format_handler import codegen_adf

from codegen_handler import write_code

from github_handler import push_branch_and_open_pr

# output to aws cloudwatch
log = logging.getLogger()
log.setLevel(logging.INFO)

def load_secrets():
  sm = boto3.client("secretsmanager")
  resp = sm.get_secret_value(SecretId="jira-to-code")
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
  expected = (os.environ.get("X_SHARED_JIRA_TOKEN") or "").strip().lower()

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

  # # Log everything so you can see it in CloudWatch
  # print("=== Incoming headers ===")
  # log.info(json.dumps(headers, ensure_ascii=False))
  # print("=== Incoming body ===")
  # log.info(json.dumps(work_item, ensure_ascii=False))

  # **************************************************************
  # send payload to llm for analysis
  # **************************************************************
  # 1) send first prompt to llm
  process_payload_response, messages = process_payload(work_item_details)

  comments1 = strip_code_fences(process_payload_response.text)
  model_signature1 = process_payload_response.llm

  # 2) add first observations of payload as a comment in jira
  add_comment(work_item, comments1, model_signature1)
  # --------------------------------------------------------------


  # **************************************************************
  # send jira use case summary and description as followup instructions
  # **************************************************************
  # 1) send jira summary and description
  response_to_jira_reqs, messages = process_jira_requirements(work_item_details, messages)

  # 2) add llm response as another comment to jira
  comments2 = strip_code_fences(response_to_jira_reqs.text)
  model_signature2 = response_to_jira_reqs.llm

  add_comment(work_item, comments2, model_signature2)
  # --------------------------------------------------------------


  # **************************************************************
  # generate code
  # **************************************************************
  # 1) prompt llm to generate project and code
  build_code_reponse, messages = build_code(work_item_details, messages)

  code_path = pathlib.Path("/tmp/codegen")

  llm_code = strip_code_fences(build_code_reponse.text)

  msg = {
    "content": [
        {"type": "text", "text": llm_code}
    ]
  }

  # 2) source code is returns in a zip file as a decoded string
  # print(f"RESPONSE_TO_CODEGEN: {llm_code}")
  encoded_code = write_code(msg, code_path)
  # print(f"ENCODED JAVA: {encoded_code}")
  # --------------------------------------------------------------


  # **************************************************************
  # push code to github
  # **************************************************************
  # 1) push generated code to github
  model_signature3 = response_to_jira_reqs.llm

  branch_name, pr_url = push_branch_and_open_pr(
    work_item, code_path, model_signature3)

  adf_body = codegen_adf(branch_name, pr_url)
  # payload_json = json.dumps(adf_body)

  # 2) give jira the locations of the branch and pull request
  add_comment(work_item, adf_body, model_signature3)
  # --------------------------------------------------------------
