"""Haber-Kurator plugin entry point (Hermes General Plugin).

The real registration logic lives in plugin_registry.py; this module
re-exports register() because the Hermes plugin loader requires
<plugin_dir>/__init__.py with a register(ctx) entry point.

The plugin's core modules are imported as the top-level `haber_kurator`
package (haber_kurator.modules.*), so this directory must be importable.
Hermes imports plugins as `hermes_plugins.<name>`, which would not make
`haber_kurator` resolvable -- add this dir to sys.path here.
"""

import os as _os
import sys as _sys

_PKG_ROOT = _os.path.dirname(_os.path.abspath(__file__))
if _PKG_ROOT not in _sys.path:
    _sys.path.insert(0, _PKG_ROOT)

from .plugin_registry import register, VERSION  # noqa: E402

__all__ = ["register", "VERSION"]
__version__ = VERSION
