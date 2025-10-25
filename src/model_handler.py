import logging, traceback, re

from textwrap import dedent

from format_handler import strip_code_fences
from format_handler import normalize_json
from format_handler import normalize_pdfs
from format_handler import pdfs_to_text
from format_handler import payload_to_chunks
from format_handler import chunks_to_blocks

from llm_providers.llm_factory import get_provider

# output to aws cloudwatch
log = logging.getLogger(__name__)

def get_tax_expert_prompt():
  return dedent("""
    You are an expert tax examiner for the IRS. 
    Your speciality is reading tax forms in JSON 
    format and applying the rules from the official 
    IRS documentation to tax forms, and their 
    relationships to one another. 

    If you don't know the answer or are unsure what 
    you are being asked to do, say so - DO NOT invent 
    a response. If you don't have enough data to work 
    with, or there is too much, say so. If you think 
    you need clarification or need more information, 
    say so and be specific. I will provide the data 
    you need.
  """).strip()


def analyze_taxform_payload(work_item_details):
  print("*** Analyzing tax form payload ***")

  payloads = normalize_json(work_item_details.get("payloads"))
  chunks = payload_to_chunks(payloads)

  user_prompt = dedent("""
    IMPORTANT: Return a BRIEF summary as 
    Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, 
    no other text. The summary MUST NOT exceed the 
    maximum size of 32K enforced by the Jira API. 
    This includes all the ADF tags included in the 
    document. STOP returning large responses.

    The title or heading of the summary should be called 
    'Payload Form Analysis'. Make sure to highlight any 
    anomolies or discrepancies in the payload.

    Make use of tables, charts, graphs, and emojis moderately 
    for visual comprehension and effect.
  """).strip()

  try:
    provider = get_provider()

    system_message = get_tax_expert_prompt()
    provider.append_system_message(system_message)
    
    full_prompt = chunks_to_blocks(chunks, user_prompt)
    provider.append_user_message(full_prompt)

    response = provider.generate(
      request_timeout=900, temperature=0.2, max_tokens=50000)
  
  except Exception as e:
    log.error("Request failed:\n%s", traceback.format_exc())
    raise HTTPException(
      status_code=400,
      detail={"error": str(e), "type": type(e).__name__}
    )

  # append llm's reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  provider.append_assistant_message(assistant_message)

  return response


def analyze_jira_requirements(work_item_details):
  print("*** Analyzing Jira summary and description ***")

  summary = work_item_details.get("summary")
  description = work_item_details.get("description")

  user_prompt = dedent(f"""
    In light of the JSON tax form payload, 
    refine your initial analysis based on the 
    following requirements defined by the jira ticket:

    Summary: {summary}\n
    Description: {description}

    These requirements must be applied to the 
    IRS JSON tax form(s) you received, and must also 
    be examined in light of the offical IRS rules.

    Make sure to highlight any anomolies or discrepancies 
    in the payload, specifically pertaining to the requirements 
    defined in the summary and description. If needed, take the 
    extra time to deliver the best results.

    Make use of tables, graphs, and emojis moderately 
    for visual comprehension and effect.
    
    The title or heading of the summary should be called 
    'Task requirements analysis'.

    IMPORTANT: Return a BRIEF summary as 
    Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, 
    no other text. The summary MUST NOT exceed the 
    maximum size of 32K enforced by the Jira API. 
    This includes all the ADF tags included in the 
    document. STOP returning large responses.
  """).strip()

  provider = get_provider()
  provider.append_user_message(user_prompt)

  # GPT needs a higher timeout :/
  response = provider.generate(
    request_timeout=900, temperature=0.2, max_tokens=20000)

  # append reply to the dialogue
  assistant_message = strip_code_fences(response.text)
  provider.append_assistant_message(assistant_message)

  return response


def analyze_irs_documents(work_item_details):
  print("*** Analyzing IRS document(s) ***")

  analysis_summary = ""

  pdfs = normalize_pdfs(work_item_details.get("pdfs"))

  provider = get_provider()

  if len(pdfs) > 0:
    pdf_texts = pdfs_to_text(pdfs)

    # docs = [Document(page_content=t, metadata={"source": f"mem:{i}"}) for i, t in enumerate(pdf_texts)]

    # splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    # chunks = splitter.split_documents(docs)

    for item in pdf_texts or []:
      instructions = dedent(f"""
        Extract the most important details of information 
        from {item["filename"]}, and return a BRIEF 1-2 page 
        bulleted summary as plain text.
      """).strip()

      user_prompt = dedent(f"""
        {instructions}\n\n<<<IRS_INSTRUCTIONS>>>\n{item}\n<<<END_INSTRUCTIONS>>>
      """).strip()

      provider.append_user_message(user_prompt)

      # GPT needs a higher timeout :/
      response = provider.generate(
        request_timeout=900, temperature=0.2, max_tokens=60000)

      analysis_summary = analysis_summary + strip_code_fences(response.text) + "\n\n"

    # append reply to the dialogue
    provider.append_assistant_message(analysis_summary)

  summary_prompt = dedent("""
    Review the summary of the IRS PDF forms that were converted 
    into plain text and find the most important, concise points 
    between the documents and the relationships between them, 
    paericularly the requirements documented in the Jira
    summary and description.

    The title or heading of the findings should be called 
    'IRS Tax Form observations'.

    REMEMBER: Return a BRIEF summary as 
    Atlassian Document Format (ADF) that can be 
    directly posted to Jira API. Return ONLY valid ADF, 
    no other text. The summary MUST NOT exceed the 
    maximum size of 32K enforced by the Jira API. 
    This includes all the ADF tags included in the 
    document. STOP returning large responses.

    Make use of tables, graphs, and emojis moderately 
    for visual comprehension and effect.
  """).strip()

  provider.append_user_message(summary_prompt)

  # GPT needs a higher timeout :/
  response = provider.generate(
    request_timeout=900, temperature=0.2, max_tokens=60000)

  assistant_message = strip_code_fences(response.text)

  # append reply to the dialogue
  provider.append_assistant_message(assistant_message)

  return response

def build_code(work_item_details):
  user_prompt = dedent("""
    You will generate the rules and logic based on the payload, 
    the summary and description recorded by the business analyst in the 
    Jira work item, as well as any additional rules and validations
    defined by official IRS documents, and code these rules into a 
    single Java Spring Boot class with JsonNode from jackson package. 
    No project, no unit tests.

    Return ONLY valid JSON with:
    {{"project":"tax-dvs","files":[{{"path":"pom.xml","content_b64":"..."}}]}}
  """).strip()

  provider = get_provider()
  provider.append_user_message(user_prompt)

  response = provider.generate(
    request_timeout=600, temperature=0.2, max_tokens=60000)

  return response


def get_architect_prompt():
  return dedent("""
    You are a senior Java developer and application architect, 
    with expertise in microservices and best practices and patterns. 
    
    You are especially skilled in reverse engineering monolithic 
    applications and code into reusable software components.
  """).strip()


def reverse_code(work_item_details):
  summary = work_item_details.get("summary")
  description = work_item_details.get("description")

  code = normalize_json(work_item_details.get("code"))
  chunks = payload_to_chunks(code)

  user_prompt = dedent(f"""
    Here is a summary and description of your task:
    
    Summary: {summary}
    Description: {description}

    Return only a JSON object with this structure (the package name should be the same in the included code):
    {{
      "files": [
        {{
          "path": "relative/path/ClassName.java",
          "package": "com.example.package",
          "content": "full Java class code"
        }}
      ]
    }}

    DO NOT tell me what you are going to do before or after in the response. Just give me the JSON only!

    Rules:
    - Keep imports minimal and correct
    - Maintain all functionality
    - Use proper package structure
    - Include all inner classes as separate files if appropriate

    Monolith:
    {chunks}
  """).strip()

  try:
    provider = get_provider()

    system_message = get_architect_prompt()
    provider.append_system_message(system_message)
    
    full_prompt = chunks_to_blocks(chunks, user_prompt)
    provider.append_user_message(full_prompt)

    response = provider.generate(
      request_timeout=900, temperature=0.2, max_tokens=50000)
    
    # append llm's reply to the dialogue
    assistant_message = strip_code_fences(response.text)
    provider.append_assistant_message(assistant_message)

    return response
  
  except Exception as e:
    log.error("Request failed:\n%s", traceback.format_exc())
    raise HTTPException(
      status_code=400, 
      detail={"error": str(e), "type": type(e).__name__}
    )
