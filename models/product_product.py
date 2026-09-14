from datetime import timedelta
from typing import Optional

from odoo import fields, models

from odoo.addons.llm_tool.decorators import llm_tool

ELIGIBILITY_DAYS = 180
DEFAULT_PAGE_LIMIT = 100
PERIOD_COUNT = 12
PERIOD_DAYS = 30
HISTORY_DAYS = PERIOD_COUNT * PERIOD_DAYS
SCHEMA_VERSION = 1


class ProductProduct(models.Model):
    _inherit = "product.product"

    @llm_tool(read_only_hint=True, idempotent_hint=True)
    def get_sold_storable_products(
        self,
        as_of: Optional[str] = None,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> dict:
        """Get sold-storable products: 180-day eligibility, 12 demand periods.

        Eligibility, demand, and on-hand quantities include every company.
        The caller's ``env.company`` is reported on the envelope only.

        Args:
            as_of: Naive UTC datetime ``YYYY-MM-DD HH:MM:SS``. Frozen on the
                first page; omitted values use server ``fields.Datetime.now()``.
            limit: Maximum number of products to return (default 100).
            offset: Number of eligible products to skip (default 0).

        Returns:
            Versioned envelope with ``schema_version``, ``as_of``, ``company_id``,
            ``has_more``, ``next_offset``, and ``products``.
        """
        as_of_dt = (
            fields.Datetime.to_datetime(as_of) if as_of else fields.Datetime.now()
        )
        as_of_str = fields.Datetime.to_string(as_of_dt)
        eligibility_start = as_of_dt - timedelta(days=ELIGIBILITY_DAYS)
        lines = self.env["sale.order.line"].sudo()
        eligibility_lines = lines.search(
            self._forecast_line_domain(
                window_start=eligibility_start,
                as_of_dt=as_of_dt,
            )
        )
        products = eligibility_lines.mapped("product_id").filtered(
            self._has_valid_default_code
        )
        products = products.sorted("id")
        page = products[offset : offset + limit]
        has_more = offset + limit < len(products)
        next_offset = offset + limit if has_more else None
        bounds = self._period_bounds(as_of_dt)
        history_start = as_of_dt - timedelta(days=HISTORY_DAYS)
        history_lines = (
            lines.search(
                self._forecast_line_domain(
                    window_start=history_start,
                    as_of_dt=as_of_dt,
                    product_ids=page.ids,
                )
            )
            if page
            else lines.browse([])
        )
        company_ids = self.env["res.company"].sudo().search([]).ids
        demand = self._demand_by_product_period(history_lines, page.ids, bounds)
        live_qty = self._qty_available_at(page, as_of_dt, company_ids)
        period_end_qty = [
            self._qty_available_at(page, end, company_ids) for _start, end in bounds
        ]
        alternatives_by_product = self._alternative_products_by_product(
            page, as_of_dt, company_ids
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "as_of": as_of_str,
            "company_id": self.env.company.id,
            "has_more": has_more,
            "next_offset": next_offset,
            "products": [
                self._product_envelope_row(
                    product,
                    bounds,
                    demand[product.id],
                    live_qty,
                    period_end_qty,
                    alternatives_by_product[product.id],
                )
                for product in page
            ],
        }

    @staticmethod
    def _forecast_line_domain(window_start, as_of_dt, product_ids=None):
        """Domain for confirmed positive-qty sale lines in a frozen window.

        Company is not part of the domain: every company's orders qualify.
        """
        domain = [
            ("order_id.state", "in", ("sale", "done")),
            ("order_id.date_order", ">=", window_start),
            ("order_id.date_order", "<", as_of_dt),
            ("product_id.type", "=", "product"),
            ("product_id", "!=", False),
            ("product_uom_qty", ">", 0),
        ]
        if product_ids is not None:
            domain.append(("product_id", "in", product_ids))
        return domain

    @staticmethod
    def _has_valid_default_code(product):
        """Return True when ``default_code`` is non-empty after stripping."""
        code = product.default_code
        return bool(code and str(code).strip())

    @staticmethod
    def _period_bounds(as_of_dt):
        """Return 12 half-open ``(start, end)`` bounds, k=0 newest."""
        bounds = []
        for index in range(PERIOD_COUNT):
            start = as_of_dt - timedelta(days=PERIOD_DAYS * (index + 1))
            end = as_of_dt - timedelta(days=PERIOD_DAYS * index)
            bounds.append((start, end))
        return bounds

    def _qty_available_at(self, products, when, company_ids):
        """On-hand quantity across all companies with ``to_date=when``."""
        dated = products.sudo().with_context(
            to_date=when,
            allowed_company_ids=list(company_ids),
        )
        return {product.id: product.qty_available for product in dated}

    def _alternative_products_by_product(self, page, as_of_dt, company_ids):
        """Map each page product id to directional alternative template rows.

        Follows ``product_tmpl_id.alternative_product_ids`` only. Skips the
        primary template, deduplicates templates, omits templates whose
        frozen on-hand is zero or negative, and loads frozen on-hand once
        for all remaining active storable variants on the page.

        Args:
            page: Eligible ``product.product`` recordset for this page.
            as_of_dt: Frozen datetime passed to ``_qty_available_at``.
            company_ids: Same company ids used for primary live stock.

        Returns:
            Dict mapping product id to a list of
            ``{id, name, skus, qty_available}`` dicts, possibly empty.
        """
        result = {product.id: [] for product in page}
        if not page:
            return result

        templates_by_product_id = {}
        remaining = self.env["product.template"]
        for product in page:
            primary_tmpl = product.product_tmpl_id
            seen = set()
            ordered = self.env["product.template"]
            for tmpl in primary_tmpl.alternative_product_ids:
                if tmpl.id == primary_tmpl.id or tmpl.id in seen:
                    continue
                seen.add(tmpl.id)
                ordered |= tmpl
            templates_by_product_id[product.id] = ordered
            remaining |= ordered

        variants = self.env["product.product"]
        qty_by_variant = {}
        if remaining:
            variants = self.env["product.product"].search(
                [
                    ("product_tmpl_id", "in", remaining.ids),
                    ("type", "=", "product"),
                ]
            )
            if variants:
                qty_by_variant = self._qty_available_at(
                    variants, as_of_dt, company_ids
                )

        variants_by_tmpl = {}
        for variant in variants:
            variants_by_tmpl.setdefault(variant.product_tmpl_id.id, []).append(
                variant
            )

        for product in page:
            items = []
            templates = templates_by_product_id[product.id].sorted(
                lambda tmpl: (tmpl.name or "", tmpl.id)
            )
            for tmpl in templates:
                tmpl_variants = variants_by_tmpl.get(tmpl.id, [])
                skus = sorted(
                    {
                        str(variant.default_code).strip()
                        for variant in tmpl_variants
                        if variant.default_code and str(variant.default_code).strip()
                    }
                )
                qty_available = sum(
                    qty_by_variant.get(variant.id, 0.0) for variant in tmpl_variants
                )
                if qty_available <= 0:
                    continue
                items.append(
                    {
                        "id": tmpl.id,
                        "name": tmpl.name,
                        "skus": skus,
                        "qty_available": qty_available,
                    }
                )
            result[product.id] = items
        return result

    def _demand_by_product_period(self, lines, product_ids, bounds):
        """Sum qualifying line qty into 12 buckets per product; missing stays 0."""
        demand = {product_id: [0.0] * PERIOD_COUNT for product_id in product_ids}
        for line in lines:
            product_id = line.product_id.id
            if product_id not in demand:
                continue
            date_order = line.order_id.date_order
            if not date_order:
                continue
            if isinstance(date_order, str):
                date_order = fields.Datetime.to_datetime(date_order)
            for index, (start, end) in enumerate(bounds):
                if start <= date_order < end:
                    demand[product_id][index] += line.product_uom_qty
                    break
        return demand

    def _product_envelope_row(
        self,
        product,
        bounds,
        period_qtys,
        live_qty,
        period_end_qty,
        alternative_products,
    ):
        """Build one product dict with identity, live stock, and period rows."""
        product_id = product.id
        return {
            "id": product_id,
            "default_code": product.default_code,
            "name": product.name,
            "qty_available": live_qty[product_id],
            "periods": [
                {
                    "start": fields.Datetime.to_string(start),
                    "end": fields.Datetime.to_string(end),
                    "ordered_qty_raw": period_qtys[index],
                    "period_end_qty": period_end_qty[index][product_id],
                }
                for index, (start, end) in enumerate(bounds)
            ],
            "alternative_products": alternative_products,
        }
