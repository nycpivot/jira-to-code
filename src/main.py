import logging, boto3, json, os, pathlib, hmac, traceback

from fastapi import FastAPI, Request, Header, HTTPException
from functools import lru_cache

from logging_handler import setup_logging

from jira_handler import load_jira
from jira_handler import add_comment

from model_handler import analyze_taxform_payload
from model_handler import analyze_irs_documents
from model_handler import analyze_jira_requirements
from model_handler import build_code
from model_handler import reverse_code

from format_handler import strip_code_fences
from format_handler import codegen_adf
from format_handler import get_merged_files_json

from codegen_handler import generate_code

from github_handler import push_files_to_branch_and_open_pr

setup_logging()

app = FastAPI(title="jira-to-code")
log = logging.getLogger(__name__)

@app.get("/healthz")
def health():
  return {"ok": True}


@app.post("/codegen")
async def gen_code(
  request: Request,
  x_shared_jira_token: str | None = Header(default=None)):
  
  incoming = (x_shared_jira_token or "").strip()
  expected = _get_expected_token()
  if not incoming or not expected or not hmac.compare_digest(incoming.lower(), expected.lower()):
    raise HTTPException(status_code=401, detail="invalid token")
  
  try:
    work_item = await request.json()

    # # Log everything so you can see it in CloudWatch
    # print("=== Incoming headers ===")
    # log.info(json.dumps(headers, ensure_ascii=False))
    log.info("*** Incoming body ***")
    log.info(json.dumps(work_item, ensure_ascii=False))

    # process jira payload
    work_item_details = load_jira(work_item)


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
    encoded_code = generate_code(msg, code_path)
    # print(f"ENCODED JAVA: {encoded_code}")
    # --------------------------------------------------------------


    # **************************************************************
    # 5) push code to github
    # **************************************************************
    # push generated code to github
    branch_name, pr_url = push_files_to_branch_and_open_pr(
      work_item, code_path, model_signature)

    adf_body = codegen_adf(branch_name, pr_url)

    # give jira the locations of the branch and pull request
    add_comment(work_item, adf_body, model_signature)
    # --------------------------------------------------------------

  except Exception as e:
    log.error("Request failed:\n%s", traceback.format_exc())
    raise HTTPException(
      status_code=400,
      detail={"error": str(e), "type": type(e).__name__}
    )

  return {"ok": True, "result": "ok"}


@app.post("/coderev")
async def rev_code(
  request: Request,
  x_shared_jira_token: str | None = Header(default=None)):
  
  incoming = (x_shared_jira_token or "").strip()
  expected = _get_expected_token()
  if not incoming or not expected or not hmac.compare_digest(incoming.lower(), expected.lower()):
    raise HTTPException(status_code=401, detail="invalid token")
  
  try:
    work_item = await request.json()

    # # Log everything so you can see it in CloudWatch
    # print("=== Incoming headers ===")
    # log.info(json.dumps(headers, ensure_ascii=False))
    log.info("*** Incoming body ***")
    log.info(json.dumps(work_item, ensure_ascii=False))

    # process jira payload
    work_item_details = load_jira(work_item)


    # **************************************************************
    # 1) send code to llm for analysis and new code in json
    # **************************************************************
    # send first prompt to llm
    rev_code_response = reverse_code(work_item_details)
    json_code_only = get_merged_files_json(rev_code_response.text)

    log.info(json_code_only)
    # --------------------------------------------------------------


    # # **************************************************************
    # # 2) push code to github
    # # **************************************************************
    # # push generated code to github
    # branch_name, pr_url = push_branch_and_open_pr(
    #   work_item, code_path, model_signature)

    # adf_body = codegen_adf(branch_name, pr_url)

    # # give jira the locations of the branch and pull request
    # add_comment(work_item, adf_body, model_signature)
    # # --------------------------------------------------------------

  except Exception as e:
    log.error("Request failed:\n%s", traceback.format_exc())
    raise HTTPException(
      status_code=400,
      detail={"error": str(e), "type": type(e).__name__}
    )

  return {"ok": True, "result": "ok"}


def _get_expected_token() -> str:
  # prefer secret value; fall back to env
  secrets = load_secrets()
  return (
    secrets.get("X_SHARED_JIRA_TOKEN") 
    or os.getenv("X_SHARED_JIRA_TOKEN") 
    or ""
  ).strip()


@lru_cache(maxsize=1)
def load_secrets() -> dict:
  sm = boto3.client("secretsmanager")
  resp = sm.get_secret_value(SecretId="jira-to-code")
  data = json.loads(resp["SecretString"])
  for k, v in data.items():
    if k not in os.environ:
      os.environ[k] = v
  return data
