=======================
Tommasi Forecast Demand
=======================

Exposes an MCP tool that returns a versioned, paginated envelope of storable
products sold on confirmed sales orders, with live on-hand quantity and 12
dense 30-day demand periods. This 15.0.3.0.0 contract is **breaking**: callers
that expected 18 periods must be upgraded.

Depends
=======

* ``llm_tool``
* ``llm_mcp_server``
* ``sale_stock``

MCP tool
========

``product.product.get_sold_storable_products``

Request
-------

* ``as_of`` (optional): naive UTC datetime ``YYYY-MM-DD HH:MM:SS``.
  Omitted on page 1 freezes server ``fields.Datetime.now()``. Later pages
  MUST pass that same ``as_of``.
* ``limit`` (optional, default 100): maximum products per page.
* ``offset`` (optional, default 0): number of eligible products to skip.

Response
--------

A JSON object (not a bare list)::

    {
      "schema_version": 1,
      "as_of": "2010-06-15 12:00:00",
      "company_id": 1,
      "has_more": false,
      "next_offset": null,
      "products": [
        {
          "id": 1,
          "default_code": "SKU",
          "name": "Name",
          "qty_available": 10.0,
          "periods": [
            {
              "start": "...",
              "end": "...",
              "ordered_qty_raw": 0.0,
              "period_end_qty": 4.0
            }
          ]
        }
      ]
    }

Eligibility
-----------

* Confirmed orders only (``sale`` / ``done``).
* Storable products (``type == 'product'``) with ``product_uom_qty > 0``.
* ``date_order`` in ``[as_of - 180 days, as_of)`` using the frozen ``as_of``,
  not live ``now()`` after freeze.
* Non-empty trimmed ``default_code`` (empty, ``False``, and whitespace-only
  codes are dropped).
* Exactly one ``company_id``: the authenticated company. Orders and stock of
  other companies are excluded.

Periods and stock
-----------------

* Eligibility stays ``[as_of - 180 days, as_of)``. Demand history for those
  SKUs covers 12 periods (360 days) and may include sales older than 180 days.
* Exactly 12 contiguous half-open 30-day periods, ``k=0`` newest:
  ``[as_of - 30*(k+1) days, as_of - 30*k days)`` as UTC-naive Odoo datetimes.
* Missing demand is ``0``, not omitted.
* Live ``qty_available`` uses company-scoped ``to_date=as_of``.
* Period-end stock uses the same definition with ``to_date=period.end``.
  Live quantity MUST equal period-0 end stock.

Pagination
----------

* ``has_more`` is true if and only if more eligible products remain.
* ``next_offset`` is the next offset, or ``null`` when the page is complete.
* ``has_more`` is true if and only if ``next_offset`` is not null (and then
  ``next_offset > offset``).
* Pages for one run share ``as_of`` and ``schema_version`` 1.

Configuration
=============

#. Install or upgrade this module (``15.0.3.0.0``).
#. The tool appears on ``/mcp`` ``tools/list``. Restart the worker if needed.
