import pathlib, re, json, base64, shutil

CODEGEN_ROOT = pathlib.Path("/tmp/codegen")
FENCE_START = re.compile(r"```json\s*", re.I)

def write_code(msg: dict, code_path: pathlib.Path = CODEGEN_ROOT) -> list[str]:
  # 1) gather text blocks
  blocks = [b.get("text","") for b in (msg.get("content") or []) if b.get("type")=="text"]
  if not blocks:
    raise ValueError("No text blocks in assistant message")
  blob = ("\n\n".join(blocks)).lstrip("\ufeff\u200b\u200c\u200d").strip()

  # 2) get JSON payload text (tolerate missing closing fence)
  m = FENCE_START.search(blob)
  candidate = blob[m.end():] if m else blob

  # 3) trim to outermost {...}
  s, e = candidate.find("{"), candidate.rfind("}")
  if s == -1 or e == -1 or e <= s:
    raise ValueError(f"No complete JSON object found (likely truncated). First 200 chars: {candidate[:200]!r}")
  payload_text = candidate[s:e+1]

  # 4) parse
  try:
    data = json.loads(payload_text)
  except json.JSONDecodeError as ex:
    raise ValueError(f"Manifest JSON decode failed at pos {ex.pos}: {ex.msg}. "
                        f"Starts: {payload_text[:200]!r}")

  files = data.get("files") or []
  if not isinstance(files, list):
    raise ValueError("Manifest 'files' must be a list")

  # 5) reset / write
  if code_path.exists():
    shutil.rmtree(code_path)
  code_path.mkdir(parents=True, exist_ok=True)

  written = []
  for f in files:
    path = f.get("path"); b64 = f.get("content_b64")
    if not path or not isinstance(b64, str): continue
    out_path = code_path / path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    written.append(str(out_path))

  return written

