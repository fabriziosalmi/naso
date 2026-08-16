"""NASO backend application package.

Explicit, empty ``__init__.py`` rather than relying on PEP 420 namespace
packages. Implicit namespace packages work until two things go wrong at once:
a stale directory on ``sys.path`` silently merges into the package, and
``pytest``'s rootdir inference picks a different import mode than the runtime
does. Both have cost this project a debugging session; the file is free.
"""
