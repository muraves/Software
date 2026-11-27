"""MURAVES shared library.

The modules below are imported on first use rather than with the
package, so that importing the shared reconstruction core
(``muraves_lib.reco``) does not require ROOT, pandas or tqdm, which only
some of them need. ``from muraves_lib import root_wrapper``,
``muraves_lib.run_manager`` and ``muraves_lib.__all__`` work as before.
"""

import importlib as _importlib

_MODULES = ("file_handler", "run_manager", "root_wrapper", "snakefile_helper")


def __getattr__(name):
    if name in _MODULES:
        return _importlib.import_module(f".{name}", __name__)

    if name == "__all__":
        # The public names of all four modules, as before. Building it
        # imports all of them, ROOT included.
        names = []
        for module in _MODULES:
            names += _importlib.import_module(f".{module}", __name__).__all__
        globals()["__all__"] = names
        return names

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    public = {name for name in globals() if not name.startswith("_") or name.startswith("__")}
    return sorted(public | set(_MODULES) | {"__all__"})
