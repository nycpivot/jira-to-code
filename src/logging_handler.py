import logging, os, boto3, watchtower

LOG_GROUP = os.getenv("CW_LOG_GROUP", "/eks/jira-to-code")
STREAM    = os.getenv("HOSTNAME", "pod")
REGION    = os.getenv("AWS_REGION", "us-east-1")

def setup_logging():
  root = logging.getLogger()
  if getattr(root, "_cw_configured", False):
    return  # avoid duplicate handlers on reload/uvicorn workers
  root.setLevel(logging.INFO)

  # stdout
  root.addHandler(logging.StreamHandler())

  # cloudwatch
  logs_client = boto3.client("logs", region_name=REGION)
  cw = watchtower.CloudWatchLogHandler(
    log_group=LOG_GROUP,
    stream_name=STREAM,
    boto3_client=logs_client,
    create_log_group=True
  )
  root.addHandler(cw)

  root._cw_configured = True  # sentinel
