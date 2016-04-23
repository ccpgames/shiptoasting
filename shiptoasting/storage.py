"""Functions related to the storage of the shiptoasts."""


import os
import html
import time
import yaml
import logging
import datetime
from collections import namedtuple

from bs4 import BeautifulSoup
from flask import abort
from gcloud import datastore
from gcloud import pubsub
from gcloud.exceptions import BadRequest
from gcloud.exceptions import NotFound

from shiptoasting import app
from shiptoasting import HEARTBEAT
from shiptoasting.formatting import format_message
from shiptoasting.kube import all_active_pods


VISIBLE_POSTS = int(os.environ.get("SHIPTOASTS_VISIBLE_MAX", 50))
SPAM_ALLOWED = bool(int(os.environ.get("SPAM_IS_ALLOWED", 0)))
KIND = os.environ.get("DATASTORE_KIND", "shiptoast")
ShipToast = namedtuple("ShipToast",
                       ("author", "author_id", "content", "time", "id"))


def _clean_content(message):
    """Cleans the message to remove any html tags from it."""

    try:
        return html.escape(" ".join(BeautifulSoup(
            message,
            "html.parser",
        ).stripped_strings))
    except Exception as error:
        logging.warning("couldn't use bs4 to parse the content for strings")
        logging.warning(error)
        abort(400)


def _time_sorted(shiptoast_list):
    """Sorts a list of shiptoasts by time posted."""

    return sorted(shiptoast_list, key=lambda k: k.time)


class ShipToastCache(list):
    """In-memory cache of shiptoasts seen by this pod."""

    def is_spam(self, shiptoast):
        """Returns a boolean of if the post is considered spam."""

        if SPAM_ALLOWED:
            return False

        # can't compare offset-naive and offset-aware datetimes
        # this error is the worst. completely avoidable, maybe worth a warning
        cutoff = shiptoast.time - datetime.timedelta(seconds=30)
        if cutoff.tzname():
            cutoff_naive = datetime.datetime.fromtimestamp(cutoff.timestamp())
        else:
            cutoff_naive = cutoff
            cutoff = datetime.datetime.fromtimestamp(
                cutoff_naive.timestamp(),
                tz=datetime.timezone.utc,
            )

        shiptoasted = 0
        for known in self:
            try:
                inside_cutoff = known.time > cutoff
            except TypeError:
                inside_cutoff = known.time > cutoff_naive

            if inside_cutoff:
                if known.author_id == shiptoast.author_id:
                    if known.content == shiptoast.content:
                        return True
                    shiptoasted += 1
                if shiptoasted >= 2:
                    return True
            else:
                break

        return False

    def inject(self, shiptoast):
        """Add a shiptoast to the front of the cache, trims the end."""

        self.insert(0, shiptoast)
        while len(self) > VISIBLE_POSTS:
            self.pop(-1)


class ShipToasts(object):
    """Singleton of shiptoasts for upload processing and retrieval/caching."""

    def __init__(self):
        self.name = os.uname()[1]

        project = os.environ.get("GCLOUD_DATASET_ID")
        if project == "None":
            project = None

        if project:
            self._client = datastore.Client(project=project)
        else:
            self._counter = 0

        self._pods = []

        if self._update_active_pods() is not None:
            self._pubsub_client = pubsub.Client(project=project)
            self._topic = self._pubsub_client.topic(self.name)
            if not self._topic.exists():
                self._topic.create()

        self._subs = []  # instances subscribed to changes
        self._queue = []   # unformatted messages to post to datastore
        self._cache = ShipToastCache()

        self._age = 0

    def initial_fill(self, update_pods=True):
        """Query the datastore for all shiptoasts, sort and cache them."""

        if not hasattr(self, "_client"):
            return  # running w/o datastore backend

        results = []
        datastore_query = self._client.query(kind=KIND, order=["-time"])
        try:
            for res in datastore_query.fetch(limit=VISIBLE_POSTS):
                results.append(ShipToast(
                    res["author"],
                    res["author_id"],
                    format_message(res["content"]),
                    res["time"],
                    res.key.id,
                ))
        except BadRequest as error:
            logging.warning(error)

        known_ids = [st.id for st in self._cache]
        for res in _time_sorted(results):
            if res.id not in known_ids and not self._cache.is_spam(res):
                self._cache.inject(res)

        if update_pods:
            self._update_active_pods()

    def periodic_call(self):
        """Called at regular intervals to clean up our cache."""

        self._age += 1

        active_pods = self._update_active_pods()

        # check memberlist for dead nodes, remove their topics
        #  needs to happen every so often, not that often
        if not self._age % 10 and active_pods is not None:
            self._remove_old_topics()

        # check datastore, fill in anything we might of missed due to race
        #   condition on startup. can disable entirely after a couple minutes
        #   except in the case of running in local dev
        if self._age < 3 or active_pods is None:
            self.initial_fill(False)

    def _update_active_pods(self):
        """Updates self._pods if there's a KubeAPI available.

        Returns:
            the return from all_active_pods
        """

        active_pods = all_active_pods()
        if active_pods is not None:
            self._pods = active_pods
        return active_pods

    def get_all_topics(self):
        """Returns a list of all topics from the pubsub client."""

        if not hasattr(self, "_pubsub_client"):
            return []  # running in dev w/o pubsub

        all_topics = []

        topics_and_page = self._pubsub_client.list_topics()
        topics, page = topics_and_page

        all_topics.extend(topics)

        while page is not None:
            topics_and_page = self._pubsub_client.list_topics(page_token=page)
            topics, page = topics_and_page
            all_topics.extend(topics)

        return all_topics

    def _remove_old_topics(self):
        """Removes old topics and subscribers to them."""

        for topic in self.get_all_topics():
            if topic.name.startswith("shiptoasting-") and \
               topic.name not in self._pods:
                for subscription in topic.list_subscriptions()[0]:
                    try:
                        subscription.delete()
                    except NotFound:
                        pass
                try:
                    topic.delete()
                except NotFound:
                    pass

    def listen_for_updates(self):
        """Sits on a pull sub to fill in live updates."""

        sub = pubsub.Client(
            project=os.environ.get("GCLOUD_DATASET_ID")
        ).topic(self.name).subscription(self.name)

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
                    yaml_shiptoast["id"],
                )
                if not self._cache.is_spam(shiptoast):
                    self._cache.inject(shiptoast)
                    self._update_subs(shiptoast)
                sub.acknowledge(message_id)

    def _add_shiptoast(self, shiptoast):
        """Adds a shiptoast to the google datastore.

        Returns:
            the ID from saving to datastore, or self._counter + 1
        """

        if hasattr(self, "_client"):
            entity = datastore.Entity(self._client.key(KIND))
            entity["author"] = shiptoast.author
            entity["author_id"] = shiptoast.author_id
            entity["content"] = shiptoast.content
            entity["time"] = shiptoast.time

            try:
                self._client.put(entity)
            except BadRequest as err:
                logging.error("Error uploading to datastore: %r", dict(entity))
                logging.error(err)
            else:
                return entity.key.id
        else:
            self._counter += 1
            return self._counter

    def _save_pending(self):
        """Tries to save all posts in the queue, requeues failures.

        Returns:
            list of authors ids whos messages were posted
        """

        posted_authors = []
        current, self._queue = self._queue, []
        for shiptoast in current:
            _id = self._add_shiptoast(shiptoast)
            if _id:
                # create the formatted message for our cache
                formatted = ShipToast(
                    shiptoast.author,
                    shiptoast.author_id,
                    format_message(shiptoast.content),
                    shiptoast.time,
                    _id,
                )

                # notify ourself clients immediately
                self._cache.inject(formatted)
                self._update_subs(formatted)

                # publish to notify running nodes
                unformatted = shiptoast._asdict()
                unformatted["id"] = _id
                as_yaml = bytes(yaml.dump(unformatted), encoding="utf-8")
                for topic in self.get_all_topics():
                    if topic.name in self._pods and topic.name != self.name:
                        topic.publish(as_yaml)
                posted_authors.append(shiptoast.author_id)
            else:
                self._queue.append(shiptoast)

        return posted_authors

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
        """Adds a shiptoast to the cache, datastore and pubsub."""

        content = _clean_content(content)
        if not content:
            # nothing after cleaning. they should also calm the fuck down
            return []

        now = datetime.datetime.now(tz=datetime.timezone.utc)

        # add to the save queue
        shiptoast = ShipToast(author, author_id, content, now, None)
        if not self._cache.is_spam(shiptoast):
            self._queue.append(shiptoast)
        return self._save_pending()

    def get_shiptoasts(self):
        """Returns the cached shiptoasts."""

        return self._cache

    def add_sub(self, poster):
        """Adds a subscriber for updates."""

        self._subs.append(poster)

    def remove_sub(self, poster):
        """Removes a subscriber from updates."""

        self._subs.remove(poster)


class ShipToaster(object):
    """Client/thread object."""

    def __init__(self, last_seen_id):

        # add ourself to subscribers at the same time as checking the cache
        cache, _ = list(app.shiptoasts._cache), app.shiptoasts.add_sub(self)

        seen_index = 0
        for i, cached in enumerate(cache):
            if cached.id == last_seen_id:
                seen_index = i
                break

        self.updates = cache[:seen_index]

        del cache
        del _

    def __del__(self):
        app.shiptoasts.remove_sub(self)

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
