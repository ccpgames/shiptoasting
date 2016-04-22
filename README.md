# ShipToasting

For when you really need to give a toast to a ship in Eve Online.


## What is this?

This is a silly thing that was made for Eve Fanfest 2016 to demonstrate some of the capabilities of Google Cloud and Kubernetes. You should have all the required pieces in this repository to be able to create your own container and deploy it on GKE. It can also serve as a point of reference for integrating EVE SSO into a python flask web app.


## How did you do the thing with the typing?

A python module called [doitlive](http://doitlive.readthedocs.org/en/latest/). The `doit.sh` script was what I used on stage (`doitlive play doit.sh`). I could of deployed the `shiptoasting-kube-all.yaml` in that script as well, but wanted to demonstrate the Kubernetes dashboard. Hence the bash-fu at the end to extract the admin password from kubectl config straight into the clipboard.


## Steps to deploy to your own GKE cluster

- Have SSL certificates made for your site, save as `key.pem` and `cert.pem` in `./ssl/`
- Make yourself a SSO API key (https://developers.eveonline.com), add it to `sso-config.json`
- Sign up for GCE and/or make a new GCE project at https://cloud.google.com/
- Enable the pubsub and datastore APIs for the project https://console.cloud.google.com/apis/
- Create a service account, download a JSON credentials file for it (moved to `./key.json`)
- Install [gcloud](https://cloud.google.com/sdk/downloads) locally
- Build the Dockerfile in this repo `docker build -t <region>.gcr.io/<project-id>/shiptoasting .`
- Push your container to gcr.io using `gcloud docker push <region>.gcr.io/<project-id>/shiptoasting`
- Use `gcloud` to install `kubectl` by running `gcloud components install kubectl`
- Create a new GKE cluster either with `gcloud` or on https://console.cloud.google.com/kubernetes/
- Give yourself `kubectl` access with `gcloud container clusters get-credentials <cluster-name>`
- Change the references in `nginx.conf` and `shiptoasting-kube-all.yaml` to your project-id and hostname
- Replace the `favicon.ico` with something else, if you want
- Run every `kubectl create` command in `doit.sh`
- Create the `ReplicationController` and `Service` objects either with `kubectl create -f shiptoasting-kube-all.yaml` or by using the dashboard
- Update public DNS using [cloud DNS](https://cloud.google.com/dns/) or your existing DNS infrastructure (`kubectl get services` to get the  loadbalancer IP)


## But I only want to run this locally!

Ok friend, no worries. Let's assume your docker host is available by name at `docker`. After copying the credentials used to the docker host (in this example, the `docker` user's home dir), you could use a `docker run` command similar to:

```bash
docker run -d --name=shiptoasting \
-p 8123:8080 \
-e FLASK_APP_SECRET_KEY=/flask/secret \
-e FLASK_HOST_NAME=http://docker:8123 \
-e EVE_SSO_CONFIG=/ccp/config.json \
-e EVE_SSO_CALLBACK=http://docker:8123/callback \
-e GCLOUD_DATASET_ID="eve-tech" \
-e GOOGLE_APPLICATION_CREDENTIALS="/google/key.json" \
-e SPAM_IS_ALLOWED=1 \
-v /home/docker/shiptoasting/ccp:/ccp \
-v /home/docker/shiptoasting/flask:/flask \
-v /home/docker/shiptoasting/google:/google \
shiptoasting:latest shiptoasting-dev
```

You'll need to change `GCLOUD_DATASET_ID` to be the project-id (name) of your GCE project. Using `shiptoasting-dev` as the run command will run the web frontend with flask only (and in debug mode), remove the command to use gunicorn (and without debug) instead.
