"""OpenEvolve integration package (legacy).

.. deprecated::
    This package is a leftover from an earlier adapter layout. The canonical
    OpenEvolve adapter is ``evoseal.integration.oe.openevolve_adapter``.
    This package's ``__init__.py`` previously attempted to import from a
    nonexistent ``.openevolve_adapter`` module, which raised ``ImportError``
    on any import. New code should import from ``evoseal.integration.oe``.
"""

__all__: list[str] = []
