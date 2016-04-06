"""ShipToasting initialization and globals."""


import os
import json
from functools import wraps

from flask import abort
from flask import Flask
from flask import redirect
from flask import session
from flask_oauthlib.client import OAuth


__version__ = "0.0.1"
app = Flask(__name__)
oauth = OAuth()
evesso = oauth.remote_app("evesso", app_key="EVESSO")


# setup flask
APP_SECRET = os.environ.get("FLASK_APP_SECRET_KEY")


if not APP_SECRET:
    raise RuntimeError("FLASK_SECRET is required!")


if os.path.isfile(APP_SECRET):
    with open(APP_SECRET, "r") as opensecret:
        APP_SECRET = opensecret.read().strip()


app.secret_key = APP_SECRET


# setup SSO
SSO_SCOPE = os.environ.get("EVE_SSO_SCOPE", "publicData")
SSO_CALLBACK = os.environ.get("EVE_SSO_CALLBACK", "")
SSO_CONFIG = os.environ.get("EVE_SSO_CONFIG")


if not SSO_CONFIG:
    raise RuntimeError("EVE_SSO_CONFIG is required!")
elif not SSO_CALLBACK:
    raise RuntimeError("EVE_SSO_CALLBACK is required!")


if os.path.isfile(SSO_CONFIG):
    try:
        with open(SSO_CONFIG, "r") as openconfig:
            app.config["EVESSO"] = json.load(openconfig)
    except Exception as error:
        raise RuntimeError("Could not read SSO CONFIG! %r", error)


oauth.init_app(app)


def requires_logged_in(func):
    """Wrap to look for the evesso_token and character session keys."""

    @wraps(func)
    def _requires_sso_token(*args, **kwargs):
        try:
            session["character"]["CharacterID"]
            session["evesso_token"][0]
        except:
            return redirect("/")
        else:
            return func(*args, **kwargs)

    return _requires_sso_token


@evesso.tokengetter
def get_evesso_oauth_token():
    return session.get("evesso_token")


@app.route("/login")
def login():
    return evesso.authorize(callback=SSO_CALLBACK, scope=SSO_SCOPE)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/callback")
def sso_callback():
    """Callback URL. Verify and creates session objects."""

    resp = evesso.authorized_response()
    if resp is None:
        abort(403)
    elif isinstance(resp, Exception):
        abort(503)

    session["evesso_token"] = resp["access_token"], ""
    session["character"] = evesso.get("verify").data

    return redirect("/")


from shiptoasting import web  # noqa
