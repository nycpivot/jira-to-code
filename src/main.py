import logging, boto3, json, os, base64, pathlib

from jira_handler import load_jira
from jira_handler import add_comment

from model_handler import analyze_taxform_payload
from model_handler import analyze_irs_documents
from model_handler import analyze_jira_requirements
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
  print("*** Incoming body ***")
  log.info(json.dumps(work_item, ensure_ascii=False))


  # **************************************************************
  # 1) send payload to llm for analysis
  # **************************************************************
  # send first prompt to llm
  taxform_analysis = analyze_taxform_payload(work_item_details)

  # create jira comment
  taxform_analysis_comments = strip_code_fences(taxform_analysis.text)
  model_signature = taxform_analysis.llm

  # post jira comment
  taxform_analysis_comments_response = add_comment(
    work_item, taxform_analysis_comments, model_signature)
  # --------------------------------------------------------------


  # **************************************************************
  # 2) send jira use case summary and description as followup instructions
  # **************************************************************
  # send jira summary and description
  jira_reqs_analysis = analyze_jira_requirements(work_item_details)

  # add llm response as another comment to jira
  jira_reqs_analysis_comments = strip_code_fences(jira_reqs_analysis.text)
  model_signature = jira_reqs_analysis.llm

  add_comment(work_item, jira_reqs_analysis_comments, model_signature)
  # --------------------------------------------------------------


  # **************************************************************
  # 3) send irs documents to llm for analysis
  # **************************************************************
  # send prompt to llm
  irs_documents_analysis = analyze_irs_documents(work_item_details)

  # add llm response as another comment to jira
  irs_documents_analysis_comments = strip_code_fences(irs_documents_analysis.text)
  model_signature = irs_documents_analysis.llm

  add_comment(work_item, irs_documents_analysis_comments, model_signature)
  # --------------------------------------------------------------


  # **************************************************************
  # 4) generate code
  # **************************************************************
  # prompt llm to generate project and code
  build_code_reponse = build_code(work_item_details)

  code_path = pathlib.Path("/tmp/codegen")

  llm_code = strip_code_fences(build_code_reponse.text)

  msg = {
    "content": [
        {"type": "text", "text": llm_code}
    ]
  }

  # source code is returned in a zip file as a decoded string
  # print(f"RESPONSE_TO_CODEGEN: {llm_code}")
  encoded_code = write_code(msg, code_path)
  # print(f"ENCODED JAVA: {encoded_code}")
  # --------------------------------------------------------------


  # **************************************************************
  # 5) push code to github
  # **************************************************************
  # push generated code to github
  branch_name, pr_url = push_branch_and_open_pr(
    work_item, code_path, model_signature)

  adf_body = codegen_adf(branch_name, pr_url)

  # give jira the locations of the branch and pull request
  add_comment(work_item, adf_body, model_signature)
  # --------------------------------------------------------------
