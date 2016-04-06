"""ShipToasting web handlers."""


import os
import sys
import atexit
import traceback

from flask import Response
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from apscheduler.schedulers.gevent import GeventScheduler

from shiptoasting import app
from shiptoasting import requires_logged_in
from shiptoasting.storage import ShipToasts
from shiptoasting.storage import ShipToaster


@app.route("/", methods=["GET"])
def index():
    """Main index. Displays most recent then streams."""

    return render_template(
        "index.html",
        shiptoasts=ShipToasts.get_shiptoasts(),
    )


@app.route("/", methods=["POST"])
@requires_logged_in
def add_shiptoast():
    """Accepts the POST form, stores the content."""

    post_content = request.form.get("content")
    if post_content:
        if len(post_content) > 500:
            post_content = "{}... and I've said too much.".format(
                post_content[:500]
            )

        # TODO: add rate limiting
        ShipToasts.add_shiptoast(
            post_content,
            session["character"]["CharacterName"],
            session["character"]["CharacterID"],
        )

    return redirect("/")


@app.route("/shiptoasts")
def shiptoasts():
    """Returns the shiptoasts stream object."""

    return Response(streaming_shiptoasts(), mimetype="text/event-stream")


def streaming_shiptoasts():
    """Iterator to asyncly deliver shiptoasts."""

    for shiptoast in ShipToaster().iter():
        data = (
            '<div class="shiptoast">'
            '<div class="shiptoaster">'
            '<div class="prof_pic"><img '
            'src="https://image.eveonline.com/Character/{author_id}_256.jpg" '
            'height="256" width="256" alt="{author}" /></div>'
            '<div class="author{ccp}">{author}</div>'
            '</div>'
            '<div class="content">{content}</div>'
            '<div class="time">{time:%b %e, %H:%M:%S}</div>'
            '</div>'
        ).format(
            ccp=" ccp" * int(shiptoast.author.startswith("CCP ")),
            **shiptoast._asdict()
        )
        yield "data: {}\n\n".format(data)

    raise StopIteration


def traceback_formatter(excpt, value, tback):
    """Catches all exceptions and re-formats the traceback raised."""

    sys.stdout.write("".join(traceback.format_exception(excpt, value, tback)))


def hook_exceptions():
    """Hooks into the sys module to set our formatter."""

    if hasattr(sys.stdout, "fileno"):  # when testing, sys.stdout is StringIO
        # reopen stdout in non buffered mode
        sys.stdout = os.fdopen(sys.stdout.fileno(), "wb", 0)
        # set the hook
        sys.excepthook = traceback_formatter


def production(*_, **settings):
    """Hooks exceptions and returns the Flask app."""

    hook_exceptions()
    ShipToasts.initial_fill()
    scheduler = GeventScheduler()
    scheduler.add_job(ShipToasts.periodic_fill, "interval", seconds=30)
    greenlet = scheduler.start()
    atexit.register(greenlet.join)
    atexit.register(scheduler.shutdown)

    return app


def development():
    """Debug/cmdline entry point."""

    production().run(
        host="0.0.0.0",
        port=8080,
        debug=True,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    development()
