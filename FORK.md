# MeshForge fork of LXMF

This is a maintained fork of [LXMF](https://github.com/markqvist/LXMF)
(Lightweight Extensible Message Format) by Mark Qvist, owned by the MeshForge
project (Nursedude). It is the messaging-layer companion to the MeshForge fork
of [Reticulum](https://github.com/Nursedude/reticulum).

## Base

- **Upstream:** `markqvist/LXMF`
- **Forked at tag:** `0.9.4` (original vendoring anchor)
- **Current base tag:** `1.0.1` (merged 2026-07-17; see Upstream merge history)
- **Fork branch:** `meshforge`
- **Version scheme:** PEP 440 local marker — `<base>+mf.0`, `<base>+mf.1`, …
  The base version is never changed independently of upstream; only the
  `+mf.N` segment increments for MeshForge changes, and it resets to `+mf.0`
  when the base is bumped to a new upstream tag.

## Upstream merge history

### `1.0.1+mf.9` → `1.0.1+mf.10` (2026-10-12) — follow rns `1.3.8+mf.7`

Pin-only release, no LXMF code change. rns `1.3.8+mf.7`: a PipeInterface
child that is behind costs a forwarding reader one wait per congestion
episode and stops flapping (caught-up persists 0.5 s, pipe sampled on waited
puts, offline offers counted, respawn closes the episode; one fresh
non-author pass on the final cut, TAG-READY, two formerly unpinned branches
now pinned red-first). Cut together with the rns tag so the pair resolves
from the tags on day one. Not rolled: no fleet box runs a PipeInterface; the
MeshForge/MeshAnchor pins stay at rns mf.5 / lxmf mf.8 until the next roll.

### `1.0.1+mf.8` → `1.0.1+mf.9` (2026-10-10) — follow rns `1.3.8+mf.6`

Pin-only release, no LXMF code change. rns `1.3.8+mf.6`: a PipeInterface
child that stops draining costs that interface, not rnsd (writer thread +
bounded queue, honest `online`; two fresh non-author passes). Cut together
with the rns tag this time, so the pair resolves from the tags on day one
(mf.8 was cut only after a fresh `pip install` of MeshForge's pin file went
ResolutionImpossible). Not rolled: no fleet box runs a PipeInterface; the
MeshForge/MeshAnchor pins stay at rns mf.5 / lxmf mf.8 until the next roll.

### `1.0.1+mf.7` → `1.0.1+mf.8` (2026-10-10) — follow rns `1.3.8+mf.5`

Pin-only release, no LXMF code change. rns `1.3.8+mf.5`: an external
interface module that calls `RNS.panic()` / `sys.exit()` while loading costs
that interface, not rnsd (five fresh non-author passes). Found the hard way:
rns was rolled fleet-wide with `--no-deps` first, every box then read
`lxmf 1.0.1+mf.6 has requirement rns==1.3.8+mf.4` under a real `pip check`,
and MeshForge CI's fresh `pip install -r requirements/rns.txt` was
`ResolutionImpossible` — the exact pin doing its job. Note: this is the first
release AFTER mf.7, so a fleet roll of mf.8 also carries mf.7's backchannel
kick (planned 2026-10-09: "roll mf.7 with the next LXMF release, not alone";
mf.7 was tagged, canaried once on one box, never rolled).

### `1.0.1+mf.6` → `1.0.1+mf.7` (2026-10-09) — the backchannel kick waits for the outbound lock

mf.6's kick started `process_outbound` in a bare thread; `process_outbound`
returns immediately when `outbound_processing_lock` is held by another peer's
reply, so under contention (several peers answering in the same tick) the kick
was lost and the message waited for the next `PROCESSING_INTERVAL` tick. Seen
on the fleet's first post-roll fire (13:10 HST): lone pairs 30–80 ms, but five
observers reading one echo at a tight 2.7–3.8 s. Fix: the kick spins on the
lock the way `handle_outbound` does, then runs. Test added to
`tests/meshforge_reconnecting_peer_link_cache.py` (fails on mf.6).

### `1.0.1+mf.5` → `1.0.1+mf.6` (2026-10-09) — a reply to a RECONNECTED peer goes now, not on a timer

Root-caused on the MeshForge fleet (the "why does moc4 answer in 9 s" question).
A long-lived LXMRouter (the lab echo) answering a peer that comes back with the
SAME identity but a NEW process (the one-shot tracer, every 600 s) paid 2–10 s
per reply while the LAN link was idle. Measured on the manager: echo cache
empty → 25 ms; 20 s later, cache holding the link to the previous (exited)
tracer process → 5,960 ms, 6,902 ms. 7 d × 4 boxes: the sub-200 ms mode was
1–4 % of fires. Echo-side RNS log at EXTREME showed the mechanism exactly:
`The link to <peer> was closed unexpectedly, retrying path request...` (the
CLOSED-cached-link branch, which schedules `DELIVERY_RETRY_WAIT` = 10 s), then
`Starting transfer` only on the next `PROCESSING_INTERVAL` (4 s) tick, once the
new peer's inbound link had identified and become a backchannel.

Three gaps in `LXMRouter`, all still in upstream master on 2026-10-09:

1. `delivery_link_closed()` was `pass`, and neither incoming delivery links nor
   outbound `RNS.Link(...)` delivery links registered a closed callback — so a
   closed/dead link stayed in `direct_links` / `backchannel_links` and was
   tried FIRST for the next message to that peer.
2. (same root) the CLOSED branch then imposes `DELIVERY_RETRY_WAIT` even though
   a path is known.
3. `delivery_remote_identified()` registered the backchannel but never kicked
   `process_outbound`, so a message already pending for that peer waited for
   the job loop (0–4 s of pure wait, every reply).

Fix (12 lines, no wire change): register `delivery_link_closed` on both link
kinds; `delivery_link_closed` forgets the link in both tables; a backchannel
arrival starts `process_outbound` when a message is pending for that peer.
Test: `tests/meshforge_reconnecting_peer_link_cache.py` (3 of 4 fail on the
unpatched tree). Live canary on the manager, both ends on this tree via
PYTHONPATH: **18 ms / 17 ms / 17 ms** for the warm-cache loopback that was
6.5 s. Pairs with MeshForge `lab/lxmf_tracer.py` tearing its links down on
exit (the party that dies closes the door) — on an mf.5 echo that teardown
alone moves the warm path from the dead-ACTIVE wait (~3 s) to the CLOSED
branch (~6.5 s), so roll this BEFORE or WITH that tracer change.

**Offer back (2026-10-09):** attempted. `gh pr create` against
`markqvist/LXMF` is refused — "Interactions on this repository have been
restricted to collaborators only" (the December 2025 Carrier Switch; see the
Reticulum fork's FORK.md). The offer therefore lives where anyone, the author
included, can take it without GitHub interactions: this fork's `master` is
upstream `master` + exactly one commit (`f28d1c8`, mf.6 + the mf.7 lock-wait
kick, 17+/1−), and the PR text is `docs/offer-back-reconnected-peer-link-cache.md`.
No other channel was posted to; that is the operator's call.

### `1.0.1+mf.4` → `1.0.1+mf.5` (2026-10-01) — follow rns `1.3.8+mf.4`

Pin-only release, no LXMF code change. rns `1.3.8+mf.4`: join-only
(`require_shared_instance`) never binds `@rns` and is retryable in-process.

### `1.0.1+mf.3` → `1.0.1+mf.4` (2026-10-01) — follow rns `1.3.8+mf.3`

Pin-only release, no LXMF code change. rns `1.3.8+mf.3`: a refused
`require_shared_instance` client (every local `rnstatus`) releases `@rns`.

### `1.0.1+mf.2` → `1.0.1+mf.3` (2026-10-01) — follow rns `1.3.8+mf.2`

Pin-only release, no LXMF code change. rns `1.3.8+mf.2` fixes
`interface_mode = gateway`/`internal` raising KeyError at startup (rnsd failed
to start). Same exact-pin coupling as below.

### `1.0.1+mf.1` → `1.0.1+mf.2` (2026-09-26) — follow rns `1.3.8+mf.1`

Pin-only release, no LXMF code change. rns `1.3.8+mf.1` fixes an AutoInterface
boot crash (rnsd exit 255 on a tentative IPv6 link-local). Because the pin
above is exact, every rns `+mf.N` release needs a matching LXMF release, or
`pip check` breaks and a clean install from `requirements/rns.txt` cannot
resolve. That coupling is the price of the exact pin, and it is paid on purpose.

### `1.0.1+mf.0` → `1.0.1+mf.1` (2026-07-19) — pin RNS exactly

Upstream declares `install_requires=["rns>=1.3.5"]`. For a FORK that range is a
live footgun, and it fired: during the 1.3.8 canary soak, stock `rns 1.3.9`
landed in the canary box's SERVICE venv beside `1.3.8+mf.0`.

The cause is PEP 440 ordering — a local version sorts ABOVE the same release,
so stock `1.3.9` sits BETWEEN our `1.3.8+mf.0` and a future `1.3.9+mf.0`. Any
resolution allowed to upgrade takes stock and silently drops the `+mf` patches
(#72 `_rpc_recv` poll, mf.4 logging-lock, mf.5 exit-75) while the version
string still reads newer.

`<1.3.9` is NOT the fix — verified against `packaging`:

| spec | stock 1.3.9 | fork 1.3.8+mf.0 | fork 1.3.9+mf.0 | old 1.2.5+mf.5 |
|---|---|---|---|---|
| `>=1.3.5` (upstream) | allowed ❌ | allowed | allowed | blocked |
| `<1.3.9` | blocked | allowed | **blocked ❌** | **allowed ❌** |
| `==1.3.8+mf.0` | blocked | allowed | blocked | blocked |

`<1.3.9` would exclude our own next fork AND still admit the pre-roll
`1.2.5+mf.5` — letting msgpack-era LXMF run against pickle-era RNS, the exact
8s-RPC-timeout split the coordinated roll exists to prevent.

So: **exact pin**. It states the invariant this fleet already lives by — rnsd
and every client roll TOGETHER — in the one place pip reads at install time.
**Bump this pin in the same commit as any RNS fork bump.**

#### What the pin does and does NOT do (measured 2026-07-19, disposable venv)

| scenario | before (`>=1.3.5`) | after (`==1.3.8+mf.0`) |
|---|---|---|
| `pip install <lxmf-fork>` alone | silently pulls stock rns | **exit 1, fails loud**: "No matching distribution found for rns==1.3.8+mf.0" — nothing installed |
| both forks in one resolution (the roll path) | ok | ok — `lxmf 1.0.1+mf.1` + `rns 1.3.8+mf.0` |
| explicit `pip install --upgrade rns` | clobbers, undetectable | **still clobbers** (pip warns, exit 0) — but now `pip check` REPORTS it |

**Be precise about the residual: an exact pin does not stop a determined
`--upgrade`.** pip prints a dependency-conflict warning and proceeds. What
changes is detectability — with `>=1.3.5`, stock 1.3.9 SATISFIED the
requirement, so `pip check` was clean and the clobber was invisible. With the
exact pin, `pip check` reports:

```
lxmf 1.0.1+mf.1 has requirement rns==1.3.8+mf.0, but you have rns 1.3.9.
```

So the pin converts a silent, undetectable failure into a loud-at-resolution
one plus a machine-checkable witness afterwards. That is the honest claim —
prevention of the accidental path, detection of the deliberate one. Wiring
`pip check` into the env-coherence probe would close the remaining gap
(``probe_rns_env_coherence`` compares versions ACROSS envs today; it does not
compare an env against its own declared requirements).

### `0.9.4+mf.0` → `1.0.1+mf.0` (2026-07-17)

Adopted upstream `1.0.1` in lockstep with the RNS `1.3.8` merge. The fork has
**zero functional patches** (marker + FORK.md + NOTICE only), so this was a
clean adoption: all `LXMF/` library code is **byte-identical to upstream
1.0.1** — the merge conflicted only on `_version.py` (the marker). No
message-format break: the new `FIELD_*` constants (REPLY_TO 0x30, REPLY_QUOTE
0x31, REACTION 0x40, COMMENT 0x41, CONTINUATION 0x42) are additive and numeric.

Lockstep compatibility verified (MeshForge + MeshAnchor share this fork; their
`canonical_message.py` bridge contract is a byte-locked twin):

- **Compression cross-compat is safe.** 1.0.1 adds compression-support
  *signalling* (`compression_support_from_app_data`), not compression itself —
  `RNS.Resource` has always defaulted `auto_compress=True`, so 0.9.4 already
  compressed and decompression is symmetric at the RNS layer. A 1.0.1 sender to
  a 0.9.4 peer sees a 2-element announce (`len < 3`) and defaults to compressing,
  exactly as before; 1.0.1 only lets a sender *skip* compression for a peer that
  explicitly opts out, which no MeshForge/MeshAnchor peer does. Safe across a
  mixed-version fleet roll.
- **No FIELD collision.** Both gateways key their bridge fields by STRING
  (`meshforge_source_network`, `meshforge_reply_to`, …), which coexist with
  LXMF's numeric field keys in the msgpack fields dict. 1.0.1 added no
  field-key validation in the pack path. Proven by round-trip: string +
  numeric keys survive `msgpack.packb`/`unpackb` together, meshforge_* fields
  intact.
- **canonical_message** has no LXMF FIELD or version dependency and stays
  byte-identical between MeshForge and MeshAnchor.

Not fleet-rolled at merge time: the `meshforge` branch stays at `0.9.4+mf.0`
until the coordinated RNS+LXMF fleet roll (canary + soak). Both apps on a box
import the same installed LXMF, so the version moves for MeshForge and
MeshAnchor together by construction.

## Why this fork exists

Same rationale as the Reticulum fork: RNS/LXMF upstream withdrew public support
("Carrier Switch", December 2025). `0.9.4` is the LXMF version field-proven on
the MeshForge fleet paired with RNS `1.2.5`. We fork to own the dependency.

## Hard invariant — DO NOT VIOLATE

**Never change the LXMF message format, field namespace, or delivery/propagation
semantics in a way that breaks interoperability** with stock LXMF, NomadNet, and
Sideband on the public Reticulum network. The fork's job is maintenance and
isolation, not redesign.

## License

Retains the upstream **Reticulum License** (see `LICENSE`). The upstream
copyright and permission notice are preserved; MeshForge modifications are
recorded in `NOTICE`. See the Reticulum fork's `FORK.md` for the license
discussion.

## Tracking upstream

Mirror the Reticulum fork's process: add upstream as a remote, merge the new
tag into `meshforge`, re-run MeshForge Phase-1 parity verification (including a
public-net LXMF round-trip to NomadNet/Sideband), canary, then fleet.
