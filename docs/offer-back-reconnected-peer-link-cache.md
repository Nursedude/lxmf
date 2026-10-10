## Problem

A long-lived `LXMRouter` answering a peer that comes back with the **same identity in a new process** (the previous process exited) replies seconds late, even on an idle LAN link.

Mechanism, traced with `RNS.loglevel = LOG_EXTREME` on the replying side:

1. `delivery_link_closed()` is a no-op, and neither incoming delivery links (`delivery_link_established`) nor outbound delivery links (`RNS.Link(...)` in `process_outbound`) register a closed callback. A closed or dead link stays in `direct_links` / `backchannel_links` and is tried **first** for the next message to that peer. The CLOSED branch then logs `The link to <peer> was closed unexpectedly, retrying path request...` and schedules `DELIVERY_RETRY_WAIT` (10 s), although a path is known.
2. `delivery_remote_identified()` stores the new backchannel but never kicks `process_outbound`, so a message already pending for that peer waits for the next `PROCESSING_INTERVAL` (4 s) job-loop tick.

The replying application itself (`handle_outbound` called within 3 ms of receipt) is not involved; the time is in the router's bookkeeping.

## Measurements (Raspberry Pi 4, shared instance, LAN)

| state of the replying router's link cache | PING→ACK round trip |
|---|---|
| empty (router just started) | 25 ms |
| holding the previous process's link, 20 s later | 5,960 ms, 6,902 ms |
| this patch on both ends, same warm-cache case | 18 ms, 17 ms, 17 ms |

On a nine-node fleet that pings every node every 10 minutes from a fresh process, the sub-200 ms mode was 1–4 % of samples before this change and is the norm after it (deployed 2026-10-09).

## Change

- Register `delivery_link_closed` on both incoming and outbound delivery links.
- `delivery_link_closed` forgets the link in both tables, so the next message does not try it.
- When a backchannel becomes available and a message is pending for that peer, start `process_outbound` — waiting for `outbound_processing_lock` the way `handle_outbound` does, because `process_outbound` returns at once when another peer's reply holds the lock and a bare thread would be lost under contention.

No timer, crypto or wire-format change. 17 insertions, 1 deletion in `LXMRouter.py`.

## Test

Our fork carries a unit test that drives the three methods on a bare `LXMRouter` (no Reticulum instance): closed links are forgotten in both tables, incoming links register the closed callback, a backchannel arrival runs `process_outbound` for a pending message (including while the lock is held by another reply) and does not when nothing is pending. Three of the four original assertions fail on upstream master. Happy to add it under `tests/` here if that fits the project's layout.

## Known limit, out of scope

A link left dead by a peer that *crashed* (no close packet) still relies on the RNS keepalive to be detected; this change only guarantees that a link which **was closed** is not reused, and that a pending message goes as soon as the new path is usable. A clean-exit client should tear its links down before exiting.
