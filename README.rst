=======================
Tommasi Forecast Demand
=======================

Exposes an MCP tool that returns a versioned, paginated envelope of storable
products sold on confirmed sales orders, with live on-hand quantity, 12
dense 30-day demand periods, and nested ``alternative_products``. This
15.0.4.0.0 contract is **breaking** for company isolation: callers that
expected one-company isolation must be upgraded. Demand and stock are
now summed across all companies. Version ``15.0.6.0.0`` is additive:
``schema_version`` stays ``1`` and each product row includes nested
``alternative_products``. The forecast agent treats that list as
informational only (buy math still uses primary ``qty_available``).

Depends
=======

* ``llm_tool``
* ``llm_mcp_server``
* ``sale_stock``
* ``website_sale`` (direct depend as of ``15.0.6.0.0``; directional
  ``product.template.alternative_product_ids``)

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
          "alternative_products": [
            {
              "id": 9,
              "name": "Alt template",
              "skus": ["ALT-A", "ALT-B"],
              "qty_available": 12.0
            }
          ],
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
* Search is **not** scoped to the caller's company. Eligibility, demand, and
  on-hand quantities include every company, even when the user is limited to
  one company. Envelope ``company_id`` is still the caller's ``env.company``.

Periods and stock
-----------------

* Eligibility stays ``[as_of - 180 days, as_of)``. Demand history for those
  SKUs covers 12 periods (360 days) and may include sales older than 180 days.
* Exactly 12 contiguous half-open 30-day periods, ``k=0`` newest:
  ``[as_of - 30*(k+1) days, as_of - 30*k days)`` as UTC-naive Odoo datetimes.
* Missing demand is ``0``, not omitted.
* Live ``qty_available`` sums on-hand across all companies with
  ``to_date=as_of``.
* Period-end stock uses the same definition with ``to_date=period.end``.
  Live quantity MUST equal period-0 end stock.
* ``alternative_products`` is a list (possibly empty) of directional
  website_sale templates. Each item is ``{id, name, skus, qty_available}``.
  There are no nested ``periods``. ``schema_version`` stays ``1``.

Alternative products
--------------------

* Directional ``product.product.product_tmpl_id.alternative_product_ids``
  only. Reverse M2M is omitted. The primary product's own template is
  skipped. Templates are deduplicated.
* One item per remaining template. ``skus`` are sorted unique non-empty
  trimmed ``default_code`` values of that template's active
  ``type == 'product'`` variants. Variants without a valid SKU still
  contribute ``qty_available`` when they are active storable.
* Frozen ``qty_available`` uses the same ``_qty_available_at`` helper,
  ``as_of``, and all-company scope as primary live stock. Alternatives
  are batch-resolved per page, not once per product row. Templates whose
  frozen on-hand is zero or negative are omitted (the list may be empty).
* The forecast-agent consumer shows this stock as a Sheet reference
  only. It MUST NOT change ``Unidades a Comprar`` or ``Stock final``.
  Roll out this addon first; roll back the agent first if the agent
  already requires the nested field.

Pagination
----------

* ``has_more`` is true if and only if more eligible products remain.
* ``next_offset`` is the next offset, or ``null`` when the page is complete.
* ``has_more`` is true if and only if ``next_offset`` is not null (and then
  ``next_offset > offset``).
* Pages for one run share ``as_of`` and ``schema_version`` 1.

Configuration
=============

#. Install or upgrade this module (``15.0.6.0.0``).
#. The tool appears on ``/mcp`` ``tools/list``. Restart the worker if needed.

Forecast agent bridge
=====================

Queued HMAC ``POST /v1/agent/invoke`` so Inventory managers can run the
forecast agent without blocking the browser. Local doodba ``devel.yaml``
attaches ``odoo`` to ``tommasi-forecast-edge`` next to Chatwoot.

Quick path
----------

#. Start the forecast-agent Compose stack first so network
   ``tommasi-forecast-edge`` exists (``docker compose -f
   docker-compose.local.yaml up --build``).
#. Recreate doodba ``odoo`` so it joins that network. Do not remove
   the existing Chatwoot external network.
#. Upgrade this module to ``15.0.5.0.0``.
#. Set Edge URL: local ``http://edge-api:8080``, production an HTTPS
   hostname with no path rewrite.
#. Provision a dedicated edge ``edge_clients`` row with
   ``streaming_allowed=FALSE``. Store the matching API key and HMAC secret
   on the company config (manager-only).
#. Run Forecast from Inventory → Forecast. Confirm the all-company
   wizard, then cron claims the queue; the form does not wait on HTTP.

Local Compose snippet
---------------------

Modeled on the existing Chatwoot ``external: true`` network
(``chatwoot_compose`` / ``chatwoot-compose_default``). Local
``devel.yaml`` already lists ``tommasi_forecast_edge`` alongside
Chatwoot. Other Compose files still need the same attach.

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
protect these Odoo columns. Restrict ``llm.group_llm_manager``. The
Inventory Forecast group can queue runs but cannot read ``api_key`` or
``hmac_secret``.

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
* Doodba ``odoo`` lists ``tommasi_forecast_edge`` next to Chatwoot in
  local ``devel.yaml``.
* Local URL is ``http://edge-api:8080``; production is HTTPS hostname.
* Edge row has ``streaming_allowed=FALSE``.
* Secrets rotated with overlap; operators know Odoo stores them
  plaintext at rest.
* Host clocks are NTP-synced; retries reuse the idempotency key only.
