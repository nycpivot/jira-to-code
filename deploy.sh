# DOCKER
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin 806869445083.dkr.ecr.us-east-1.amazonaws.com

docker build -t 806869445083.dkr.ecr.us-east-1.amazonaws.com/private/jira-to-code:latest .

docker push 806869445083.dkr.ecr.us-east-1.amazonaws.com/private/jira-to-code:latest

kubectl delete -f deployment.yaml
kubectl apply -f deployment.yaml
kubectl get pods -w