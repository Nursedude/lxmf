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
