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

#. Install or upgrade this module (``15.0.5.0.0``).
#. The tool appears on ``/mcp`` ``tools/list``. Restart the worker if needed.

Forecast agent bridge
=====================

Queued HMAC ``POST /v1/agent/invoke`` so Inventory managers can run the
forecast agent without blocking the browser. This addon documents the
doodba attach snippet; it does **not** edit parent ``devel.yaml``.

Quick path
----------

#. Start the forecast-agent Compose stack first so network
   ``tommasi-forecast-edge`` exists.
#. Attach doodba ``odoo`` to that network (snippet below). Do not remove
   the existing Chatwoot external network.
#. Upgrade this module to ``15.0.5.0.0``.
#. Set Edge URL: local ``http://edge-api:8080``, production an HTTPS
   hostname with no path rewrite.
#. Provision a dedicated edge ``edge_clients`` row with
   ``streaming_allowed=FALSE``. Store the matching API key and HMAC secret
   on the company config (manager-only).
#. Run Forecast from Inventory / Reporting. Cron claims the queue; the
   form does not wait on HTTP.

Local Compose snippet
---------------------

Modeled on the existing Chatwoot ``external: true`` network
(``chatwoot_compose`` / ``chatwoot-compose_default``). Add
``tommasi_forecast_edge`` **alongside** those entries. Parent doodba
``devel.yaml`` is out of this addon's edit authority — copy the snippet
when you have a later grant.

On the ``odoo`` service, keep ``default`` and any existing externals,
then add::

    # Reach local forecast edge-api for queued HMAC invoke.
    # Start the forecast-agent stack first so external network
    # tommasi-forecast-edge exists.
    networks:
      default:
      chatwoot_compose:
      tommasi_forecast_edge:

At the Compose ``networks:`` root, add::

    tommasi_forecast_edge:
      external: true
      name: tommasi-forecast-edge

Doodba's default network is internal. Without this attach, Odoo cannot
resolve ``http://edge-api:8080`` even when the config URL is correct.

Edge URL
--------

=============  ==========================================================
Environment    Value
=============  ==========================================================
Local          ``http://edge-api:8080`` (HTTP allowed in ``devel`` /
               ``test`` or when ``test_enable`` is set)
Production     HTTPS hostname, for example
               ``https://forecast-edge.example.com``. Terminate TLS
               without rewriting the path. HMAC signs
               ``/v1/agent/invoke`` exactly as the edge sees it.
=============  ==========================================================

Do not put userinfo in the URL. Do not call LangGraph ``:8000`` from
Odoo.

Edge client
-----------

Use a dedicated ``edge_clients`` row, not a Chatwoot key. Set
``streaming_allowed=FALSE``: this client sends ``response_mode=sync``
and must not be allowed SSE. Scopes belong on the edge; this module
stores optional ``assistant_id`` but does **not** send it on invoke.

Secrets, rotation, plaintext at rest
------------------------------------

``api_key`` and ``hmac_secret`` are stored as ordinary Odoo fields:
plaintext in Postgres and in backups. Edge Fernet encryption does **not**
protect these Odoo columns. Restrict ``llm.group_llm_manager``.

Rotate after the edge row exists (and after any suspected leak):

#. Insert a **new active** edge client (new API key and HMAC secret).
#. Save the new credentials on the Odoo company config while both edge
   rows stay active.
#. After traffic and in-flight retries have moved, deactivate the old
   edge row. Do not delete it until retries that still hold the old
   idempotency key have finished.

Never commit credentials. Never paste secrets into this README, tickets,
or logs.

Clock sync
----------

HMAC ``X-Timestamp`` is Unix epoch seconds. NTP-sync the Odoo host and
the edge host. The edge rejects timestamps outside
``EDGE_HMAC_TIMESTAMP_TOLERANCE_SECONDS`` (default ``300``). Clock skew
beyond that window looks like a ``401``, not a retryable transport error.

Retry and idempotency
---------------------

Each run gets one idempotency key at create (``X-Idempotency-Key``).
Every attempt **reuses** that key and **must** send a new timestamp,
nonce, and signature. Reusing a nonce is a ``401`` replay.

===========  ============================================================
Class        HTTP / condition
===========  ============================================================
Retryable    ``202``, ``429``, ``502``, ``503``, ``504``, transport
             failure. Bounded backoff; ``429`` may honor ``Retry-After``.
Terminal     ``401``, ``403``, ``409``, ``422``, other statuses, or
             exhausted ``max_attempts``.
===========  ============================================================

Checklist
---------

* Forecast-agent stack is up; ``tommasi-forecast-edge`` exists.
* Doodba ``odoo`` lists ``tommasi_forecast_edge`` next to Chatwoot; parent
  ``devel.yaml`` was not edited by this addon.
* Local URL is ``http://edge-api:8080``; production is HTTPS hostname.
* Edge row has ``streaming_allowed=FALSE``.
* Secrets rotated with overlap; operators know Odoo stores them
  plaintext at rest.
* Host clocks are NTP-synced; retries reuse the idempotency key only.
