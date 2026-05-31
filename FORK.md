# MeshForge fork of LXMF

This is a maintained fork of [LXMF](https://github.com/markqvist/LXMF)
(Lightweight Extensible Message Format) by Mark Qvist, owned by the MeshForge
project (Nursedude). It is the messaging-layer companion to the MeshForge fork
of [Reticulum](https://github.com/Nursedude/reticulum).

## Base

- **Upstream:** `markqvist/LXMF`
- **Forked at tag:** `0.9.4`
- **Base commit:** `2ad82b68bde5d76dfee2b333e06079fd43bbc13f`
- **Fork branch:** `meshforge`
- **Version scheme:** PEP 440 local marker — `0.9.4+mf.0`, `0.9.4+mf.1`, …
  The base version is never changed independently of upstream; only the
  `+mf.N` segment increments for MeshForge changes.

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
