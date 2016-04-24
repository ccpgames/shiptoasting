mv ~/Downloads/Eve*.json .
mv Eve*.json key.json
ls
kubectl create secret generic shiptoasting-gcloud-secret --from-file=key.json
kubectl get secrets
cat sso-config.json | grep -v secret
kubectl create secret generic shiptoasting-sso-secret --from-file=sso-config.json
kubectl get secrets
kubectl get secret shiptoasting-sso-secret -o yaml | grep sso-config.json | cut -d ':' -f2 | sed 's/^ *//' | base64 -D | grep -v secret
kubectl create configmap shiptoasting-nginx-config --from-file=$(pwd)/nginx.conf
kubectl get configmap
kubectl get configmap shiptoasting-nginx-config -o yaml
random_string 256
kubectl create secret generic shiptoasting-flask-app --from-literal=secret=$(random_string 512)
kubectl create secret generic ccp-favicon --from-file=favicon.ico
kubectl create secret generic tech-ccp-is-certs --from-file=$(pwd)/ssl
kubectl get secrets
kubectl cluster-info
kubectl config view | grep -A4 $(kubectl config current-context) | grep password | cut -d ':' -f2 | sed 's/^ *//' | pbcopy
echo "done"
