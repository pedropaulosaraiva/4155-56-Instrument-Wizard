"""
gui_text/documentation_pages/
-----------------------------
Markdown bodies for the documentation pages — one module per page, so each
(potentially very large) page lives in its own script.

Each page module exposes a single ``BODY`` string holding the Markdown content.
They are imported here so ``documentation.py`` can reach them as
``documentation_pages.<name>.BODY`` and map each to a ``DocTopic``.

To add a documentation page
---------------------------
1. Create a module here (e.g. ``stop_condition.py``) with a ``BODY`` string.
2. Import it below and list it in ``__all__``.
3. Map a ``DocTopic`` to ``<name>.BODY`` in ``gui_text/documentation.py``
   (the ``DOC_BODIES`` registry).
"""

from . import measurement_ranges, welcome

__all__ = [
    "measurement_ranges",
    "welcome",
]
