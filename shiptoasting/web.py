"""ShipToasting web handlers."""


import os
import sys
import atexit
import random
import traceback

import gevent
from flask import Response
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from apscheduler.schedulers.gevent import GeventScheduler

from shiptoasting import app
from shiptoasting import HEARTBEAT
from shiptoasting import requires_logged_in
from shiptoasting.storage import ShipToasts
from shiptoasting.storage import ShipToaster


@app.route("/", methods=["GET"])
def index():
    """Main index. Displays most recent then streams."""

    shiptoasts = app.shiptoasts.get_shiptoasts()
    return render_template(
        "index.html",
        shiptoasts=shiptoasts,
        last_seen=shiptoasts[0].id if shiptoasts else None,
    )


@app.route("/", methods=["POST"])
@requires_logged_in
def add_shiptoast():
    """Accepts the POST form, stores the content."""

    post_content = request.form.get("content").strip()
    if post_content:
        if len(post_content) > 500:
            post_content = "{}... and I've said too much.".format(
                post_content[:500]
            )

        posted_authors = app.shiptoasts.add_shiptoast(
            post_content,
            session["character"]["CharacterName"],
            session["character"]["CharacterID"],
        )

        if session["character"]["CharacterID"] not in posted_authors:
            # spam filtered, time to calm the fuck down
            enhance_your_calm_videos = [
                "eCidRemUTKo",
                "tYg6nP7yRRk",
                "txQ6t4yPIM0",
                "EYi5aW1GdUU",
                "d-diB65scQU",
            ]
            return redirect("https://www.youtube.com/watch?v={}".format(
                random.choice(enhance_your_calm_videos)
            ))

    return redirect("/")


@app.route("/shiptoasts")
def shiptoasts():
    """Returns the shiptoasts stream object."""

    last_seen_id = request.args.get("last_seen", "None")
    if last_seen_id == "None":
        last_seen_id = None
    else:
        last_seen_id = int(last_seen_id)

    return Response(
        streaming_shiptoasts(last_seen_id),
        mimetype="text/event-stream",
    )


def streaming_shiptoasts(last_seen_id):
    """Iterator to asyncly deliver shiptoasts."""

    for shiptoast in ShipToaster(last_seen_id).iter():
        if shiptoast is HEARTBEAT:
            data = HEARTBEAT
        else:
            data = (
                '{id}%{author}%'
                '<div class="shiptoaster">'
                '<div class="prof_pic"><img src='
                '"https://image.eveonline.com/Character/{author_id}_256.jpg" '
                'height="256" width="256" alt="{author}" /></div>'
                '<div class="author{ccp}">{author}</div>'
                '</div>'
                '<div class="content">{content}</div>'
                '<div class="time">{time:%b %e, %H:%M:%S}</div>'
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

    app.shiptoasts = ShipToasts()
    app.shiptoasts.initial_fill()

    scheduler = GeventScheduler()
    scheduler.add_job(app.shiptoasts.periodic_call, "interval", seconds=30)
    cleaner = scheduler.start()
    listener = gevent.Greenlet.spawn(app.shiptoasts.listen_for_updates)

    atexit.register(cleaner.join, timeout=2)
    atexit.register(listener.join, timeout=2)
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
