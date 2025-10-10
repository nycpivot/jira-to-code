import re, json

from typing import List, Dict, Any

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


def normalize_json(files):
  """
  Process ONLY JSON files:
    - Detect by MIME (application/json) or .json extension
    - Decode UTF-8 -> 'text'
    - Parse JSON -> 'json'
  Non-JSON files are passed through with metadata only (no bytes).
  """
  out = []
  for f in files or []:
    g = {k: v for k, v in f.items() if k != "bytes"}  # drop raw bytes
    b = f.get("bytes")
    name = (f.get("filename") or "").lower()
    mime = (f.get("mimeType") or "").lower()

    if not b:
      out.append(g); continue

    is_json = mime.startswith("application/json") or name.endswith(".json")
    if not is_json:
      # do NOT process non-JSON here
      out.append(g); continue

    txt = b.decode("utf-8", "replace")
    g["text"] = txt
    try:
      g["json"] = json.loads(txt)
    except json.JSONDecodeError:
      pass

    out.append(g)

  return out


def normalize_pdfs(files):
  """
  Process ONLY PDF files:
    - Detect by MIME (application/pdf) or .pdf extension
    - Keep binary safely as base64 and record size
  Non-PDF files are passed through with metadata only (no bytes).
  """
  out = []
  for f in files or []:
    g = {k: v for k, v in f.items() if k != "bytes"}  # drop raw bytes
    b = f.get("bytes")
    name = (f.get("filename") or "").lower()
    mime = (f.get("mimeType") or "").lower()

    if not b:
      out.append(g); continue

    is_pdf = mime.startswith("application/pdf") or name.endswith(".pdf")
    if not is_pdf:
      # do NOT process non-PDF here
      out.append(g); continue

    g["b64"] = base64.b64encode(b).decode("ascii")
    g["size"] = len(b)

    out.append(g)

  return out


def payload_to_chunks(data, per_file_limit=50000, total_limit=100000):
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


def chunks_to_blocks(chunks: List[str], trailer_instruction: str) -> List[Dict[str, Any]]:
  """Turn chunk strings into 'content' blocks and append your instruction."""
  blocks = [{"type": "text", "text": c} for c in chunks]
  if trailer_instruction:
    blocks.append({"type": "text", "text": trailer_instruction})
  return blocks


def strip_empty_headings(adf_doc):
  if adf_doc.get("type") == "doc":
    content = adf_doc.get("content", [])
    adf_doc["content"] = [
      n for n in content
      if not (n.get("type") == "heading" and not n.get("content"))
    ]
  return adf_doc


def wrap_table_text_in_paragraph(node):
  if isinstance(node, dict):
    t = node.get("type")
    # Wrap text-only content for header/cell
    if t in ("tableCell", "tableHeader"):
      content = node.get("content", [])
      if content and all(child.get("type") == "text" for child in content if isinstance(child, dict)):
        node["content"] = [{
          "type": "paragraph",
          "content": content
        }]
    # Recurse
    for k, v in list(node.items()):
      if isinstance(v, (dict, list)):
        node[k] = wrap_table_text_in_paragraph(v)
  elif isinstance(node, list):
    node = [wrap_table_text_in_paragraph(x) for x in node]
  return node


def codegen_adf(branch_name: str, pr_url: str) -> dict:
  return {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "heading",
        "attrs": {"level": 1},
        "content": [{"type": "text", "text": "Codegen Output"}]
      },
      {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": [
          {
            "type": "tableRow",
            "content": [
              {
                "type": "tableHeader",
                "content": [
                  {"type": "paragraph", "content": [{"type": "text", "text": "Item"}]}
                ]
              },
              {
                "type": "tableHeader",
                "content": [
                  {"type": "paragraph", "content": [{"type": "text", "text": "Value"}]}
                ]
              }
            ]
          },
          {
            "type": "tableRow",
            "content": [
              {
                "type": "tableCell",
                "content": [
                  {"type": "paragraph", "content": [{"type": "text", "text": "Branch Name"}]}
                ]
              },
              {
                "type": "tableCell",
                "content": [
                  {"type": "paragraph", "content": [{"type": "text", "text": branch_name}]}
                ]
              }
            ]
          },
          {
            "type": "tableRow",
            "content": [
              {
                "type": "tableCell",
                "content": [
                  {"type": "paragraph", "content": [{"type": "text", "text": "Pull Request"}]}
                ]
              },
              {
                "type": "tableCell",
                "content": [
                  {
                    "type": "paragraph",
                    "content": [
                      {
                        "type": "text",
                        "text": pr_url,
                        "marks": [
                          {"type": "link", "attrs": {"href": pr_url}}
                        ]
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }

