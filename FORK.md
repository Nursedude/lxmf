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
