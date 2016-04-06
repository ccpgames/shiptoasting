"""Functions related to the storage of the shiptoasts."""


import os
import time
import logging
from collections import namedtuple
from datetime import datetime

from bs4 import BeautifulSoup
from gcloud import datastore
from oauth2client.client import GoogleCredentials

from shiptoasting.formatting import format_message


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
    except Exception as err:
        logging.error("Error uploading %r to datastore: %r", dict(entity), err)
        return False


def _time_sorted(shiptoast_list):
    """Sorts a list of shiptoasts by time posted."""

    return sorted(shiptoast_list, key=lambda k: k.time, reverse=True)


class ShipToasts(object):
    """Singleton of shiptoasts for upload processing and retrieval/caching."""

    _client = datastore.Client(
        project=os.environ.get("GCLOUD_DATASET_ID"),
        credentials=GoogleCredentials.get_application_default(),
    )
    _subs = []   # instances subscribed to changes
    _cache = []  # all shiptoasts
    _queue = []  # shiptoasts yet to be saved to datastore

    @staticmethod
    def initial_fill():
        """Query the datastore for all shiptoasts, sort and cache them."""

        results = []
        datastore_query = ShipToasts._client.query(kind=KIND, order=["time"])
        for res in datastore_query.fetch(limit=VISIBLE_POSTS):
            results.append(ShipToast(
                res["author"],
                res["author_id"],
                format_message(res["content"]),
                res["time"],
            ))

        for res in _time_sorted(results):
            ShipToasts._cache.append(res)

    @staticmethod
    def periodic_fill():
        """Queury for all shiptoasts, update the cache with any missing."""

        results = []
        datastore_query = ShipToasts._client.query(kind=KIND, order=["time"])
        for res in datastore_query.fetch(limit=VISIBLE_POSTS):
            results.append(ShipToast(
                res["author"],
                res["author_id"],
                format_message(res["content"]),
                res["time"],
            ))

        cache = ShipToasts._cache
        cross_notify = []
        for res in results:
            if res not in cache:
                cache.append(res)
                cross_notify.append(res)

        for shiptoast in _time_sorted(cross_notify):
            ShipToasts._update_subs(shiptoast)

        ShipToasts._cache = _time_sorted(cache)
        ShipToasts._periodic_delete()

    @staticmethod
    def periodic_delete():
        """Periodically delete posts older than quantity."""

        # TODO: see if we want to do this or not first
        # TODO: prune the cache size
        pass

    @staticmethod
    def _save_pending():
        """Tries to save all posts in the queue, requeues failures."""

        current, ShipToasts._queue = ShipToasts._queue, []
        for shiptoast in current:
            if not _add_shiptoast(ShipToasts._client, shiptoast):
                ShipToasts._queue.append(shiptoast)

    @staticmethod
    def _update_subs(shiptoast):
        """Notify the subs of the shiptoast, removes any that fail."""

        to_remove = []
        for sub in ShipToasts._subs:
            try:
                sub.notify(shiptoast)
            except:
                to_remove.append(sub)

        for sub in to_remove:
            ShipToasts.remove_subscriber(sub)

    @staticmethod
    def add_shiptoast(content, author, author_id):
        """Adds a shiptoast to the cache and the datastore."""

        content = _clean_content(content)
        now = datetime.utcnow()

        # save/add the unformatted version to the save queue
        shiptoast = ShipToast(author, author_id, content, now)
        ShipToasts._queue.append(shiptoast)
        ShipToasts._save_pending()

        # add the formatted version to the cache, inform subscribers
        formatted = ShipToast(author, author_id, format_message(content), now)
        ShipToasts._cache.insert(0, formatted)
        ShipToasts._update_subs(formatted)

    @staticmethod
    def get_shiptoasts(quantity=VISIBLE_POSTS):
        """Returns the last $quantity shiptoasts."""

        return ShipToasts._cache[:quantity]

    @staticmethod
    def add_subscriber(poster):
        """Adds a subscriber for updates."""

        ShipToasts._subs.append(poster)

    @staticmethod
    def remove_subscriber(poster):
        """Removes a subscriber from updates."""

        ShipToasts._subs.remove(poster)


class ShipToaster(object):
    """Client/thread object."""

    def __init__(self):
        self.updates = []
        ShipToasts.add_subscriber(self)

    def __del__(self):
        ShipToasts.remove_subscriber(self)

    def notify(self, shiptoast):
        """Notify method to receive cached events."""

        self.updates.append(shiptoast)

    def iter(self):
        """Iterator of the most recent shiptoasts (blocking)."""

        while True:
            sent = []
            for shiptoast in self.updates:
                sent.append(shiptoast)
                yield shiptoast
            for shiptoast in sent:
                self.updates.remove(shiptoast)

            time.sleep(1)
