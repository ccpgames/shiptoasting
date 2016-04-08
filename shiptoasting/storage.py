"""Functions related to the storage of the shiptoasts."""


import os
import time
import yaml
import logging
from collections import namedtuple
from datetime import datetime
from datetime import timezone

from bs4 import BeautifulSoup
from gcloud import datastore
from gcloud import pubsub
from gcloud.exceptions import BadRequest
from gcloud.exceptions import NotFound

from shiptoasting import app
from shiptoasting import HEARTBEAT
from shiptoasting.formatting import format_message
from shiptoasting.kube import all_active_pods


VISIBLE_POSTS = int(os.environ.get("SHIPTOASTS_VISIBLE_MAX", 50))
KIND = os.environ.get("DATASTORE_KIND", "shiptoast")
ShipToast = namedtuple("ShipToast", ("author", "author_id", "content", "time"))


def _clean_content(message):
    """Cleans the message to remove any html tags from it."""

    return " ".join(BeautifulSoup(message, "html.parser").stripped_strings)


def _add_shiptoast(client, shiptoast):
    """Adds a shiptoast to the google datastore."""

    entity = datastore.Entity(client.key(KIND))
    entity["author"] = shiptoast.author
    entity["author_id"] = shiptoast.author_id
    entity["content"] = shiptoast.content
    entity["time"] = shiptoast.time

    try:
        client.put(entity)
        logging.info("uploaded shiptoast to google datastore")
        return True
    except BadRequest as err:
        logging.error("Error uploading to datastore: %r", dict(entity))
        logging.error(err)
        return False


def _time_sorted(shiptoast_list):
    """Sorts a list of shiptoasts by time posted."""

    return sorted(shiptoast_list, key=lambda k: k.time, reverse=True)


class ShipToasts(object):
    """Singleton of shiptoasts for upload processing and retrieval/caching."""

    def __init__(self):
        self.name = os.uname()[1]

        self._client = datastore.Client(
            project=os.environ.get("GCLOUD_DATASET_ID"),
        )

        self._pubsub_client = pubsub.Client(
            project=os.environ.get("GCLOUD_DATASET_ID"),
        )

        self._topic = self._pubsub_client.topic("shiptoasts")
        if not self._topic.exists():
            self._topic.create()

        # make a new client for the push to not collide with the read socket
        self._push_topic = pubsub.Client(
            project=os.environ.get("GCLOUD_DATASET_ID"),
        ).topic("shiptoasts")

        self._subs = []   # instances subscribed to changes
        self._cache = []  # all shiptoasts
        self._queue = []  # shiptoasts yet to be saved to datastore

    def initial_fill(self):
        """Query the datastore for all shiptoasts, sort and cache them."""

        results = []
        datastore_query = self._client.query(kind=KIND, order=["time"])
        try:
            for res in datastore_query.fetch(limit=VISIBLE_POSTS):
                results.append(ShipToast(
                    res["author"],
                    res["author_id"],
                    format_message(res["content"]),
                    res["time"],
                ))
        except BadRequest as error:
            logging.warning(error)

        for res in _time_sorted(results):
            self._cache.append(res)

    def listen_for_updates(self):
        """Sits on a pull sub to fill in live updates."""

        sub = self._topic.subscription(self.name, ack_deadline=10)
        if not sub.exists():
            sub.create()

        while True:
            for message_id, message in sub.pull():
                yaml_shiptoast = yaml.load(message.data)
                shiptoast = ShipToast(
                    yaml_shiptoast["author"],
                    yaml_shiptoast["author_id"],
                    format_message(yaml_shiptoast["content"]),
                    yaml_shiptoast["time"],
                )
                self._cache.insert(0, shiptoast)
                self._update_subs(shiptoast)
                sub.acknowledge(message_id)

    def periodic_delete(self):
        """Periodically delete posts older than quantity."""

        self._cache = self._cache[:VISIBLE_POSTS]

    def _save_pending(self):
        """Tries to save all posts in the queue, requeues failures."""

        current, self._queue = self._queue, []
        for shiptoast in current:
            if not _add_shiptoast(self._client, shiptoast):
                self._queue.append(shiptoast)

    def _update_subs(self, shiptoast):
        """Notify the subs of the shiptoast, removes any that fail."""

        to_remove = []
        for sub in self._subs:
            try:
                sub.notify(shiptoast)
            except:
                to_remove.append(sub)

        for sub in to_remove:
            self.remove_subscriber(sub)

    def add_shiptoast(self, content, author, author_id):
        """Adds a shiptoast to the cache and the datastore."""

        content = _clean_content(content)
        now = datetime.now(tz=timezone.utc)

        # add to the save queue
        shiptoast = ShipToast(author, author_id, content, now)
        self._queue.append(shiptoast)
        self._save_pending()

        # publish to notify running nodes
        self._push_topic.publish(
            bytes(yaml.dump(shiptoast._asdict()), encoding="utf-8")
        )

    def get_shiptoasts(self, quantity=VISIBLE_POSTS):
        """Returns the last $quantity shiptoasts."""

        return self._cache[:quantity]

    def add_subscriber(self, poster):
        """Adds a subscriber for updates."""

        self._subs.append(poster)

    def remove_subscriber(self, poster):
        """Removes a subscriber from updates."""

        self._subs.remove(poster)

    def remove_subscriptions(self):
        """Removes old subscriptions from the topic."""

        # NB: ideally the app would clean its own on exit. however, I could
        #     not do anything with gevent.signal, atexit, or signal directly.
        active_pods = all_active_pods()

        if active_pods is None:
            return  # running in dev, try not to destroy prod

        for sub in self._topic.list_subscriptions()[0]:
            if sub.name not in active_pods:
                try:
                    sub.delete()
                except NotFound:
                    pass  # race condition, deleted already by another pod


class ShipToaster(object):
    """Client/thread object."""

    def __init__(self):
        self.updates = []
        app.shiptoasts.add_subscriber(self)

    def __del__(self):
        app.shiptoasts.remove_subscriber(self)

    def notify(self, shiptoast):
        """Notify method to receive cached events."""

        self.updates.append(shiptoast)

    def iter(self):
        """Iterator of the most recent shiptoasts (blocking)."""

        heartbeat = 0
        while True:
            sent = []
            for shiptoast in self.updates:
                sent.append(shiptoast)
                yield shiptoast
            for shiptoast in sent:
                self.updates.remove(shiptoast)

            heartbeat += 1
            if heartbeat > 14:
                yield HEARTBEAT
                heartbeat = 0

            time.sleep(1)
