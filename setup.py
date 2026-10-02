import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

exec(open("LXMF/_version.py", "r").read())

setuptools.setup(
    name="lxmf",
    version=__version__,
    author="Mark Qvist",
    author_email="mark@unsigned.io",
    description="Lightweight Extensible Message Format for Reticulum",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/markqvist/lxmf",
    packages=["LXMF", "LXMF.Utilities"],
    license="Reticulum License",
    license_files = ("LICENSE"),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points= {
        'console_scripts': [
            'lxmd=LXMF.Utilities.lxmd:main',
        ]
    },
    # PINNED EXACTLY to the MeshForge RNS fork, deliberately (2026-07-19).
    #
    # Upstream ships `rns>=1.3.5`. That is unsafe for this fork because PEP 440
    # orders a local version ABOVE the same release: stock `1.3.9` sits between
    # our `1.3.8+mf.0` and a future `1.3.9+mf.0`. So an unpinned range lets pip
    # "upgrade" us onto STOCK rns, silently dropping the +mf patches (#72
    # _rpc_recv poll, mf.4 logging-lock, mf.5 exit-75) while the version string
    # still looks newer. That already happened once, on the 1.3.8 canary box:
    # stock 1.3.9 landed in the SERVICE venv beside the fork.
    #
    # `<1.3.9` does NOT fix it: it would also exclude our own future
    # `1.3.9+mf.0`, AND it would still admit the old `1.2.5+mf.5` — letting
    # msgpack-era LXMF run against pickle-era RNS, the 8s-RPC-timeout split the
    # coordinated roll exists to prevent.
    #
    # An exact pin is the honest expression of the invariant: rnsd and every
    # client are rolled TOGETHER, so lxmf must name the exact RNS substrate it
    # was built against. Bump this in the same commit as any RNS fork bump.
    install_requires=["rns==1.3.8+mf.4"],
    python_requires=">=3.7",
)
