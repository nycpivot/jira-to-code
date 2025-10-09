sam build
sam deploy --no-confirm-changeset

jira_token=$(cat jira-token.txt)

curl -X POST "https://xkyxz9zr7j.execute-api.us-east-1.amazonaws.com" \
      -H "Content-Type: application/json" \
      -H "X-SHARED-JIRA-TOKEN: ${jira_token}" \
      --data-binary @jira-payload.json \
      >/tmp/task.log 2>&1 &

disown
