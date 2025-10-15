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


# manual troubleshooting
kubectl logs deploy/jira-to-code --tail=200