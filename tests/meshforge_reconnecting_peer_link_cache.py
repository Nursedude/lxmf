"""mf.6 — a reply to a peer that reconnected must not wait on a dead link.

Root-caused on the MeshForge fleet 2026-10-09 (lab tracer: one-shot process every
600 s with a persistent identity; echo: long-lived LXMRouter). Measured on the
manager: with the echo's link cache EMPTY a loopback PING+ACK is 25 ms; 20 s
later, with the cache holding the link to the PREVIOUS tracer process, 5,960 ms
and 6,902 ms. Over 7 d on four boxes the sub-200 ms mode was 1-4% of fires.

Three gaps in LXMRouter, all still present in upstream master (checked 2026-10-09):
  1. delivery_link_closed() is `pass` and incoming delivery links never register
     a closed callback -> a closed/dead link stays in direct_links /
     backchannel_links and hijacks the next message to that peer (the CLOSED
     branch then schedules DELIVERY_RETRY_WAIT = 10 s).
  2. outbound delivery links (RNS.Link(...) in process_outbound) register no
     closed callback either.
  3. delivery_remote_identified() registers the backchannel but never kicks
     process_outbound, so a message already pending for that peer waits for
     the next PROCESSING_INTERVAL (4 s) job-loop tick.

These tests exercise the three methods on a bare LXMRouter (no Reticulum
instance) — they pin the bookkeeping, not the network.
"""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import RNS  # noqa: E402  (installed; no Reticulum instance is created here)
from LXMF.LXMRouter import LXMRouter  # noqa: E402


def _bare_router():
    r = LXMRouter.__new__(LXMRouter)
    r.direct_links = {}
    r.backchannel_links = {}
    r.pending_outbound = []
    r.outbound_processing_lock = threading.Lock()
    r.process_outbound = MagicMock(name="process_outbound")
    return r


def test_closed_delivery_link_is_forgotten_everywhere():
    r = _bare_router()
    dead, other = MagicMock(name="dead"), MagicMock(name="other")
    r.direct_links = {b"peer-a": dead, b"peer-b": other}
    r.backchannel_links = {b"peer-a": dead, b"peer-c": dead}
    r.delivery_link_closed(dead)
    assert r.direct_links == {b"peer-b": other}
    assert r.backchannel_links == {}


def test_incoming_delivery_link_registers_the_closed_callback():
    r = _bare_router()
    link = MagicMock()
    r.delivery_link_established(link)
    link.set_link_closed_callback.assert_called_once_with(r.delivery_link_closed)


def test_backchannel_arrival_kicks_outbound_for_a_waiting_message():
    r = _bare_router()
    identity = RNS.Identity()
    dest_hash = RNS.Destination.hash_from_name_and_identity("lxmf.delivery", identity)
    waiting = MagicMock()
    waiting.get_destination.return_value.hash = dest_hash
    r.pending_outbound = [waiting]
    link = MagicMock()
    r.delivery_remote_identified(link, identity)
    assert r.backchannel_links[dest_hash] is link
    deadline = time.time() + 2
    while not r.process_outbound.called and time.time() < deadline:
        time.sleep(0.02)
    assert r.process_outbound.called, "pending message waited for the job loop"


def test_backchannel_arrival_without_a_waiting_message_does_not_kick():
    r = _bare_router()
    identity = RNS.Identity()
    r.delivery_remote_identified(MagicMock(), identity)
    time.sleep(0.1)
    assert not r.process_outbound.called
