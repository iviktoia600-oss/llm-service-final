import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock


def key_for(endpoint, payload):
    encoded = json.dumps([endpoint, payload], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class Cache:
    def __init__(self, ttl, clock=time.monotonic, limit=512):
        self.ttl, self.clock, self.limit = ttl, clock, limit
        self.items = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= self.clock():
                del self.items[key]
                return None
            self.items.move_to_end(key)
            return value

    def put(self, key, value):
        with self.lock:
            self.items[key] = (self.clock() + self.ttl, value)
            self.items.move_to_end(key)
            if len(self.items) > self.limit:
                self.items.popitem(last=False)
