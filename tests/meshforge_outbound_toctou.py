"""mf.12 — process_outbound must not check-then-act on the link tables.

mf.6 (22e0a7c) made ``delivery_link_closed`` forget a closed link in
``direct_links`` / ``backchannel_links``. RNS fires that callback from
whichever thread closes the link (link watchdog, remote teardown), so it can
run BETWEEN process_outbound's ``h in self.direct_links`` and the
``self.direct_links[h]`` / ``.pop(h)`` that follows: KeyError in the job loop,
which skips the rest of that outbound pass. Found by the non-author read of
mf.11 (2026-10-16), queued, fixed here. Upstream's callback is ``pass``, so
only a link added or removed by another thread could reach these lines there.

The second hazard is the callback itself: it built its list by iterating
``table.items()`` live, so a link registered by another thread mid-scan raised
``RuntimeError: dictionary changed size during iteration`` (mf.11's class, in
the callback instead of clean_links).

``_RacingTable`` makes the interleaving deterministic: on its Nth membership
test it answers True and then drops the key — exactly what the closed
callback does from another thread in that gap.
"""
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import RNS  # noqa: E402  (installed; no Reticulum instance is created here)
from LXMF.LXMRouter import LXMRouter  # noqa: E402
from LXMF.LXMessage import LXMessage  # noqa: E402

H = b"d" * 16


class _RacingTable(dict):
    """dict whose ``race_on``-th ``in`` says True, then loses the key."""

    def __init__(self, *a, race_on=1, **kw):
        super().__init__(*a, **kw)
        self.race_on = race_on
        self.calls = 0

    def __contains__(self, k):
        self.calls += 1
        hit = dict.__contains__(self, k)
        if self.calls == self.race_on:
            dict.pop(self, k, None)     # the closed callback, other thread
            return True
        return hit


def _router(direct, backchannel=None):
    r = LXMRouter.__new__(LXMRouter)
    r.direct_links = direct
    r.backchannel_links = backchannel if backchannel is not None else {}
    r.pending_outbound = []
    r.outbound_processing_lock = threading.Lock()
    r.delivery_destinations = {}
    r.available_tickets = {"last_deliveries": {}}
    return r


def _msg(state, method=LXMessage.DIRECT):
    m = MagicMock()
    m.state = state
    m.method = method
    m.delivery_attempts = 0
    m.progress = None
    m.include_ticket = False
    m.get_destination.return_value.hash = H
    m.destination_hash = H
    del m.next_delivery_attempt         # hasattr() must be False
    return m


def _run(r):
    with patch.object(RNS.Transport, "has_path", return_value=False), \
         patch.object(RNS.Transport, "request_path"), \
         patch.object(RNS.Reticulum, "get_instance", side_effect=RuntimeError("bare")):
        r.process_outbound()


def test_delivered_backchannel_lookup_survives_the_closed_callback():
    """2554: `in direct_links` → callback pops → `direct_links[h]` KeyError."""
    r = _router(_RacingTable({H: MagicMock()}))
    m = _msg(LXMessage.DELIVERED)
    r.pending_outbound = [m]
    _run(r)                                   # raised KeyError
    assert r.pending_outbound == []


def test_direct_link_lookup_survives_the_closed_callback():
    """2624: the DIRECT branch's `in` / `[h]` pair."""
    r = _router(_RacingTable({H: MagicMock()}))
    m = _msg(LXMessage.OUTBOUND)
    r.pending_outbound = [m]
    _run(r)                                   # raised KeyError
    # One lookup leaves no gap to race: the link is found (pending) or not
    # (a new attempt) — either is correct; a KeyError that drops the pass is not.
    assert r.pending_outbound == [m]


def test_backchannel_lookup_survives_the_closed_callback():
    """2631: the backchannel `in` / `[h]` pair."""
    r = _router({}, _RacingTable({H: MagicMock()}))
    m = _msg(LXMessage.OUTBOUND)
    r.pending_outbound = [m]
    _run(r)                                   # raised KeyError
    assert r.pending_outbound == [m]


def test_closed_link_cleanup_survives_the_closed_callback():
    """2666: CLOSED branch `in` → callback pops → `.pop(h)` KeyError."""
    link = MagicMock()
    link.status = RNS.Link.CLOSED
    link.activated_at = 1.0
    r = _router(_RacingTable({H: link}, race_on=2))   # 1st `in` real, 2nd races
    m = _msg(LXMessage.OUTBOUND)
    r.pending_outbound = [m]
    _run(r)                                   # raised KeyError
    assert H not in dict.keys(r.direct_links)
    m.set_delivery_destination.assert_called_with(None)


def test_closed_callback_survives_a_concurrent_registration():
    """delivery_link_closed scanned table.items() live; a link registered by
    another thread mid-scan raised RuntimeError. Real threads, not staged."""
    r = _router({})
    stop = threading.Event()
    errors = []

    def writer():
        i = 0
        # Bounded: an unbounded add-only writer grew the table to 6.4 GB on
        # the FIXED code (each round copies it) and the memcg OOM-killed the
        # run. 20k adds is ~2 MB and still races the unfixed scan every time.
        while not stop.is_set() and i < 20000:
            k = (b"w%d" % i).ljust(16, b"0")
            # ADD only, as delivery_link_established does from another thread:
            # an add+pop pair between two scan steps leaves the size equal and
            # CPython's changed-size check never fires (it passed on old code).
            r.direct_links[k] = object()
            i += 1

    for i in range(2000):
        r.direct_links[(b"s%d" % i).ljust(16, b"0")] = object()
    # A list comprehension over 64 links finishes inside CPython's 5 ms
    # switch interval, so the race never ran (this test PASSED on the unfixed
    # code at first). Force switches so the writer gets in mid-scan.
    old = sys.getswitchinterval()
    t = threading.Thread(target=writer, daemon=True)
    try:
        # inside the try: a failed start() must not leak 1 µs into the session
        sys.setswitchinterval(1e-6)
        t.start()
        for _ in range(300):
            try:
                r.delivery_link_closed(object())
            except RuntimeError as e:          # noqa: PERF203
                errors.append(repr(e))
    finally:
        stop.set()
        if t.is_alive():
            t.join(5)
        sys.setswitchinterval(old)
    assert errors == [], errors[:3]
