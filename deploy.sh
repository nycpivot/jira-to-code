# DOCKER
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin 806869445083.dkr.ecr.us-east-1.amazonaws.com

docker build -t 806869445083.dkr.ecr.us-east-1.amazonaws.com/private/jira-to-code:latest .

docker push 806869445083.dkr.ecr.us-east-1.amazonaws.com/private/jira-to-code:latest

# EKS CLUSTER
eksctl create cluster --name jira-to-code --managed --region us-east-1 --instance-types t3.medium --version 1.33 --with-oidc -N 1

rm .kube/config

aws eks update-kubeconfig --name jira-to-code --region us-east-1

kubectl config rename-context arn:aws:eks:us-east-1:806869445083:cluster/jira-to-code jira-to-code
kubectl config use-context jira-to-code

kubectl apply -f deployment.yaml
#kubectl apply -f ingress.yaml

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.yaml


# sa
aws eks describe-cluster --name jira-to-code --query "cluster.identity.oidc.issuer" --output text

aws iam create-role \
  --role-name jira-to-code-secrets \
  --assume-role-policy-document file://trust-policy.json

# 1) Attach inline policy to your app role (IRSA) for CloudWatch Logs writes
aws iam put-role-policy \
  --role-name jira-to-code-secrets \
  --policy-name cw-logs-write \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "LogsManage",
        "Effect": "Allow",
        "Action": ["logs:CreateLogGroup"],
        "Resource": "*"
      },
      {
        "Sid": "LogsWrite",
        "Effect": "Allow",
        "Action": [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ],
        "Resource": [
          "arn:aws:logs:us-east-1:806869445083:log-group:/eks/jira-to-code",
          "arn:aws:logs:us-east-1:806869445083:log-group:/eks/jira-to-code:*"
        ]
      }
    ]
  }'


kubectl apply -f sa.yaml
kubectl set serviceaccount deploy/jira-to-code jira-to-code







# manual troubleshooting
kubectl logs deploy/jira-to-code --tail=200