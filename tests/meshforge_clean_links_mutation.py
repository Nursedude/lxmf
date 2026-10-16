"""mf.11 — clean_links() must not iterate a dict its own teardown mutates.

Seen on the MeshForge fleet (2026-10-16, while tracing an unrelated incident):
``LXMRouter.clean_links: RuntimeError: dictionary changed size during
iteration`` from the job loop — moc's gateway 126–154x/day on every full day
of journal (from 10-11), meshanchor-server in bursts, untracked anywhere. The
job loop logs and retries 4 s later, so it never paged; it was noise nobody had
named. Each one also SKIPS the rest of clean_links for that tick (propagation
link cleanup, outbound propagation link reset).

Cause (ours): mf.6 (22e0a7c, 2026-10-09) gave ``delivery_link_closed`` a body
that forgets a closed link in ``direct_links``. clean_links iterates
``direct_links`` and calls ``link.teardown()`` inside the loop; a teardown that
fires the closed callback pops from the dict being iterated. Upstream's
``delivery_link_closed`` is ``pass``, so upstream only has the milder form (a
link added by another thread mid-iteration). The second hazard is the same
root: the later ``self.direct_links.pop(link_hash)`` raises KeyError for an
entry the callback already removed.

Bare LXMRouter (no Reticulum instance), the REAL delivery_link_closed.
"""
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import RNS  # noqa: E402  (installed; no Reticulum instance is created here)
from LXMF.LXMRouter import LXMRouter  # noqa: E402


def _bare_router():
    r = LXMRouter.__new__(LXMRouter)
    r.direct_links = {}
    r.backchannel_links = {}
    r.validated_peer_links = {}
    r.active_propagation_links = []
    r.outbound_propagation_link = None
    r.pending_outbound = []
    r.outbound_processing_lock = threading.Lock()
    return r


class _Link:
    """Stands in for RNS.Link: inactive for ``idle`` s; teardown() fires the
    closed callback synchronously, as an RNS link closing locally may."""

    def __init__(self, router, idle, link_id=b"x"):
        self._router = router
        self._idle = idle
        self.link_id = link_id
        self.status = RNS.Link.ACTIVE
        self.torn_down = False

    def no_data_for(self):
        return self._idle

    def teardown(self):
        self.torn_down = True
        self.status = RNS.Link.CLOSED
        self._router.delivery_link_closed(self)   # the REAL mf.6 callback


def test_teardown_firing_the_closed_callback_does_not_break_the_loop():
    r = _bare_router()
    stale = _Link(r, idle=LXMRouter.LINK_MAX_INACTIVITY + 1, link_id=b"stale")
    fresh = _Link(r, idle=1, link_id=b"fresh")
    r.direct_links = {b"a" * 16: stale, b"b" * 16: fresh}
    r.clean_links()                                  # raised RuntimeError
    assert stale.torn_down
    assert list(r.direct_links.values()) == [fresh]


def test_the_rest_of_clean_links_still_runs_after_a_teardown():
    """Each RuntimeError also skipped the propagation-link cleanup below it."""
    r = _bare_router()
    r.direct_links = {b"a" * 16: _Link(
        r, idle=LXMRouter.LINK_MAX_INACTIVITY + 1)}
    prop = MagicMock()
    prop.no_data_for.return_value = LXMRouter.P_LINK_MAX_INACTIVITY + 1
    r.active_propagation_links = [prop]
    r.clean_links()
    assert r.active_propagation_links == []
    prop.teardown.assert_called_once()


def test_a_link_added_mid_iteration_survives_and_does_not_raise():
    """The upstream form: another thread registers a link while the job loop
    walks the table."""
    r = _bare_router()

    class _Adder(_Link):
        def no_data_for(self):
            r.direct_links[b"new" + b"0" * 13] = _Link(r, idle=0, link_id=b"new")
            return 0

    r.direct_links = {b"a" * 16: _Adder(r, idle=0)}
    r.clean_links()
    assert b"new" + b"0" * 13 in r.direct_links


def test_concurrent_writers_never_raise():
    """A real race, not a staged one: a writer thread churns the table while
    clean_links runs. Old code: RuntimeError within a few hundred rounds."""
    r = _bare_router()
    stop = threading.Event()
    errors = []

    def writer():
        i = 0
        while not stop.is_set():
            k = (b"w%d" % i).ljust(16, b"0")
            r.direct_links[k] = _Link(r, idle=0, link_id=k)
            r.direct_links.pop(k, None)
            i += 1

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    try:
        for _ in range(3000):
            r.direct_links.setdefault(b"s" * 16, _Link(
                r, idle=LXMRouter.LINK_MAX_INACTIVITY + 1))
            try:
                r.clean_links()
            except (RuntimeError, KeyError) as e:   # noqa: PERF203
                errors.append(repr(e))
    finally:
        stop.set()
        t.join(5)
    assert errors == [], errors[:3]
