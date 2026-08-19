"""
A paginator that does not run ``COUNT(*)`` on the big tables.

Django's admin changelist calls ``paginator.count`` on every page load. On an
append-only table with millions of rows that is a full sequential scan — on
Postgres, ``COUNT(*)`` cannot use an index-only scan for an unfiltered count,
so the cost grows linearly with the table while the page the admin actually
renders stays a fixed 100 rows.

This replaces the exact count with the planner's own row estimate from
``pg_class.reltuples``, which is free. The number shown is approximate, and
that is the correct trade: nobody paginating a pageview log needs to know that
there are exactly 4,182,331 rows rather than about 4.2 million.

The exact count is still used below ``PAGINATOR_COUNT_LIMIT``, so small tables
and filtered views report precisely.
"""
from __future__ import annotations

import logging

from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

from .defaults import get_setting

logger = logging.getLogger(__name__)


class EstimatedCountPaginator(Paginator):
    """Paginator that estimates the row count for large, unfiltered querysets."""

    @cached_property
    def count(self) -> int:
        """
        Return an exact count when it is cheap, an estimate when it is not.

        A filtered queryset always counts exactly: the estimate comes from
        table statistics and knows nothing about a WHERE clause, so using it
        there would report the whole table for a filtered page.
        """
        if self.object_list.query.where:
            return super().count

        estimate = self._estimate()
        if estimate is None or estimate < get_setting('PAGINATOR_COUNT_LIMIT'):
            return super().count
        return estimate

    def _estimate(self) -> int | None:
        """Read the planner's row estimate, or None if unavailable."""
        if connection.vendor != 'postgresql':
            return None

        table = self.object_list.model._meta.db_table
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT reltuples::bigint FROM pg_class WHERE relname = %s', [table]
                )
                row = cursor.fetchone()
        except Exception:
            logger.debug('Row estimate unavailable for %s', table, exc_info=True)
            return None

        if not row or row[0] is None or row[0] < 0:
            # -1 means the table has never been analysed, so there is no
            # estimate to use yet.
            return None
        return int(row[0])
