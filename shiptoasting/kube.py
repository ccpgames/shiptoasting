"""For working with the Kubernetes API."""


import os

import requests


# standard location for gke containers
CACRT = str("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")


class KubeAPI(object):
    """Stores the automatically injected kube API token."""

    def __init__(self):
        self.base_url = KubeAPI._api_version()

    @staticmethod
    def _api_version():
        """Determines the available api version(s)."""

        if not hasattr(KubeAPI, "base_url"):
            port = int(os.environ.get("KUBERNETES_SERVICE_PORT", "443"))
            url = "http{}://{}:{}/api/".format(
                "s" * int(port == 443),
                os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes"),
                port,
            )
            res = requests.get(url, headers=KubeAPI.headers(), verify=CACRT)
            res.raise_for_status()
            KubeAPI.base_url = url + res.json()["versions"][0]

        return KubeAPI.base_url

    @staticmethod
    def headers():
        """Returns the default token content in a headers dict."""

        token_file = "/var/run/secrets/kubernetes.io/serviceaccount/token"

        if not hasattr(KubeAPI, "_token"):
            with open(token_file, "r") as opentoken:
                KubeAPI._token = opentoken.read().strip()

        return {
            "Authorization": "Bearer {}".format(KubeAPI._token)
        }

    def get(self, url="", base_url=None):
        """Request a URL from the kube API, returns JSON loaded response."""

        res = requests.get(
            "{}/{}".format(self.base_url, url),
            headers=KubeAPI.headers(),
            verify=CACRT,
        )
        res.raise_for_status()
        return res.json()


def all_active_pods():
    """Returns a list of the active shiptoasting pods."""

    active_pods = []
    for pod in KubeAPI().get("pods")["items"]:
        if pod["metadata"].get("labels", {}).get("name") == "shiptoasting":
            active_pods.append(pod["metadata"]["name"])
    return active_pods
