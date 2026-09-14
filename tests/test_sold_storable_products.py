"""TransactionCase tests for ``product.product.get_sold_storable_products``."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Isolated from the devel catalog (recent 180-day sales) and still in the past
# so to_date historical stock and "sale after as_of" replay stay meaningful.
FROZEN_AS_OF = "2010-06-15 12:00:00"


@tagged("post_install", "-at_install")
class TestSoldStorableProducts(TransactionCase):
    """Inclusion and exclusion rules for the sold-storable MCP tool."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Forecast Demand Partner"})
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.warehouse = False
        if "stock.warehouse" in cls.env:
            cls.warehouse = cls.env["stock.warehouse"].search(
                [("company_id", "=", cls.env.company.id)], limit=1
            )

    def _create_product(self, name, default_code, product_type="product"):
        """Create a product variant with the given type and SKU."""
        return self.env["product.product"].create(
            {
                "name": name,
                "default_code": default_code,
                "type": product_type,
                "list_price": 10.0,
                "uom_id": self.uom_unit.id,
                "uom_po_id": self.uom_unit.id,
            }
        )

    def _line_vals(self, product, qty=1.0, warehouse=None):
        """Build one sale order line; set custom warehouse when the field exists."""
        warehouse = warehouse if warehouse is not None else self.warehouse
        vals = {
            "name": product.name,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "price_unit": product.list_price or 10.0,
        }
        if warehouse and "custom_warehouse_id" in self.env["sale.order.line"]._fields:
            vals["custom_warehouse_id"] = warehouse.id
        return vals

    def _create_order(
        self,
        products,
        confirm=True,
        date_order=None,
        company=None,
        line_qty=1.0,
        warehouse=None,
    ):
        """Create a sale order with one line per product.

        Args:
            products: iterable of distinct ``product.product`` records.
            confirm: if True, confirm the order to state ``sale`` / ``done``.
            date_order: optional datetime written after confirm (or on create
                when the order stays draft).
            company: optional ``res.company``; other-company orders skip
                ``action_confirm`` (no CoA) and force ``state='sale'``.
            line_qty: quantity written on every line.
            warehouse: optional warehouse for the order and custom line field.
        """
        env_sale = self.env["sale.order"]
        if company:
            env_sale = env_sale.with_company(company)
        warehouse = warehouse if warehouse is not None else self.warehouse
        if company and warehouse is self.warehouse:
            warehouse = env_sale.env["stock.warehouse"].search(
                [("company_id", "=", company.id)], limit=1
            )
        vals = {
            "partner_id": self.partner.id,
            "order_line": [
                (0, 0, self._line_vals(product, qty=line_qty, warehouse=warehouse))
                for product in products
            ],
        }
        if company:
            vals["company_id"] = company.id
        if warehouse and "warehouse_id" in env_sale._fields:
            vals["warehouse_id"] = warehouse.id
        if date_order and not confirm:
            vals["date_order"] = date_order
        order = env_sale.create(vals)
        if confirm:
            if company and company.id != self.env.company.id:
                order.write({"state": "sale"})
            else:
                self._confirm_order(order)
            if date_order:
                order.write({"date_order": date_order})
                env_sale.flush(["date_order"])
        return order

    def _confirm_order(self, order):
        """Confirm a sale order, setting delivery when the delivery app is present."""
        carrier = False
        if "delivery.carrier" in self.env:
            carrier = self.env["delivery.carrier"].search([], limit=1)
        if (
            carrier
            and hasattr(order, "set_delivery_line")
            and "delivery_set" in order._fields
            and not order.delivery_set
        ):
            order.set_delivery_line(carrier, 0.0)
        elif carrier and "carrier_id" in order._fields and not order.carrier_id:
            order.write({"carrier_id": carrier.id})
        order.action_confirm()
        return order

    def _sold_envelope(self, as_of=None, limit=100, offset=0, company=None):
        """Call the MCP tool and return the versioned envelope."""
        products = self.env["product.product"]
        if company:
            products = products.with_company(company)
        kwargs = {"limit": limit, "offset": offset}
        if as_of is not None:
            if not isinstance(as_of, str):
                as_of = fields.Datetime.to_string(as_of)
            kwargs["as_of"] = as_of
        return products.get_sold_storable_products(**kwargs)

    def _set_on_hand(self, product, qty, warehouse, company=None, move_date=None):
        """Set counted on-hand qty via inventory adjustment.

        When ``move_date`` is set, backdate the inventory move so ``to_date``
        historical qty_available can see it.
        """
        quants = self.env["stock.quant"]
        if company:
            quants = quants.with_company(company)
        quant = quants.with_context(inventory_mode=True).create(
            {
                "product_id": product.id,
                "location_id": warehouse.lot_stock_id.id,
                "inventory_quantity": qty,
            }
        )
        quant.action_apply_inventory()
        if move_date:
            moves = self.env["stock.move"].search(
                [
                    ("product_id", "=", product.id),
                    ("is_inventory", "=", True),
                ],
                order="id desc",
                limit=1,
            )
            moves.write({"date": move_date})
            if moves.move_line_ids:
                moves.move_line_ids.write({"date": move_date})
        return quant

    def _sold_rows(self, **kwargs):
        return self._sold_envelope(**kwargs)["products"]

    def _sold_ids(self, **kwargs):
        return [row["id"] for row in self._sold_rows(**kwargs)]

    def _row_for(self, product, **kwargs):
        for row in self._sold_rows(**kwargs):
            if row["id"] == product.id:
                return row
        return None

    def _create_template_with_variants(
        self, name, codes_by_value, product_type="product"
    ):
        """Create a template with one attribute and one variant per value.

        Args:
            name: Template name.
            codes_by_value: Mapping of attribute value name to
                ``default_code``. Empty or false codes still create the
                variant.
            product_type: Template ``type`` (``product``, ``consu``,
                ``service``).
        """
        attribute = self.env["product.attribute"].create(
            {
                "name": "FD Attr %s" % name,
                "create_variant": "always",
            }
        )
        values = self.env["product.attribute.value"]
        for value_name in codes_by_value:
            values |= self.env["product.attribute.value"].create(
                {
                    "name": value_name,
                    "attribute_id": attribute.id,
                }
            )
        template = self.env["product.template"].create(
            {
                "name": name,
                "type": product_type,
                "list_price": 10.0,
                "uom_id": self.uom_unit.id,
                "uom_po_id": self.uom_unit.id,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, values.ids)],
                        },
                    )
                ],
            }
        )
        for variant in template.product_variant_ids:
            value_name = variant.product_template_attribute_value_ids[:1].name
            variant.default_code = codes_by_value.get(value_name)
        return template

    def _variant_for(self, template, value_name):
        """Return the variant whose attribute value name matches ``value_name``."""
        for variant in template.product_variant_ids:
            if variant.product_template_attribute_value_ids[:1].name == value_name:
                return variant
        return self.env["product.product"]

    def _link_alternative(self, product, template):
        """Point ``product``'s template at ``template`` as a directional alternative."""
        product.product_tmpl_id.write(
            {"alternative_product_ids": [(4, template.id)]}
        )

    def _sold_primary(self, name, default_code):
        """Create a coded storable SKU with a confirmed sale in the frozen window."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product(name, default_code)
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=1.0,
        )
        return product

    def _assert_confirmed(self, order):
        """Tommasi may auto-close confirmed orders to ``done``."""
        self.assertIn(order.state, ("sale", "done"))

    def test_storable_sold_recently_is_included(self):
        """Storable products on a recent confirmed order are returned."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Sold Storable Recent", "FD-STOR-RECENT")
        order = self._create_order(
            [product], confirm=True, date_order=as_of - timedelta(days=10)
        )
        self._assert_confirmed(order)
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertIsNotNone(row)
        self.assertGreaterEqual(
            set(row.keys()),
            {
                "id",
                "default_code",
                "name",
                "qty_available",
                "periods",
                "alternative_products",
            },
        )
        self.assertEqual(row["id"], product.id)
        self.assertEqual(row["default_code"], product.default_code)
        self.assertEqual(row["name"], product.name)

    def test_consumable_and_service_sold_recently_are_excluded(self):
        """Consumable and service products are excluded even when sold recently."""
        storable = self._create_product("Sold Storable Keep", "FD-STOR-KEEP")
        consumable = self._create_product(
            "Sold Consumable", "FD-CONSU", product_type="consu"
        )
        service = self._create_product(
            "Sold Service", "FD-SERV", product_type="service"
        )
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        self._create_order(
            [storable, consumable, service],
            confirm=True,
            date_order=as_of - timedelta(days=10),
        )
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertIn(storable.id, sold_ids)
        self.assertNotIn(consumable.id, sold_ids)
        self.assertNotIn(service.id, sold_ids)

    def test_storable_on_draft_and_cancel_is_excluded(self):
        """Storable products on draft or cancelled orders are excluded."""
        draft_product = self._create_product("Draft Storable", "FD-STOR-DRAFT")
        cancel_product = self._create_product("Cancel Storable", "FD-STOR-CANCEL")
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        draft_order = self._create_order(
            [draft_product], confirm=False, date_order=in_window
        )
        self.assertEqual(draft_order.state, "draft")
        cancel_order = self._create_order(
            [cancel_product], confirm=True, date_order=in_window
        )
        cancel_order.action_cancel()
        self.assertEqual(cancel_order.state, "cancel")
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertNotIn(draft_product.id, sold_ids)
        self.assertNotIn(cancel_product.id, sold_ids)

    def test_storable_on_old_confirmed_order_is_excluded(self):
        """Storable products on confirmed orders older than 180 days are excluded."""
        old_product = self._create_product("Old Confirmed Storable", "FD-STOR-OLD")
        recent_product = self._create_product(
            "Recent Confirmed Storable", "FD-STOR-NOW"
        )
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        old_order = self._create_order(
            [old_product],
            confirm=True,
            date_order=as_of - timedelta(days=200),
        )
        self._create_order(
            [recent_product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
        )
        self._assert_confirmed(old_order)
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertNotIn(old_product.id, sold_ids)
        self.assertIn(recent_product.id, sold_ids)

    def test_duplicate_lines_and_orders_return_one_row(self):
        """The same variant appears once across two confirmed orders.

        WMS forbids two lines with the same product on one SO, so uniqueness
        is covered via two separate confirmed orders (``mapped("product_id")``).
        """
        product = self._create_product("Duplicate Storable", "FD-STOR-DUP")
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        self._create_order([product], confirm=True, date_order=in_window)
        self._create_order([product], confirm=True, date_order=in_window)
        matching = [
            row
            for row in self._sold_rows(as_of=FROZEN_AS_OF)
            if row["id"] == product.id
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["default_code"], product.default_code)
        self.assertEqual(matching[0]["name"], product.name)

    def test_get_sold_storable_products_is_llm_tool(self):
        """Apexive registers the method as ``llm.tool`` for ``llm_mcp_server``."""
        method = type(self.env["product.product"]).get_sold_storable_products
        self.assertTrue(getattr(method, "_is_llm_tool", False))
        tools = self.env["llm.tool"].search(
            [
                ("decorator_model", "=", "product.product"),
                ("decorator_method", "=", "get_sold_storable_products"),
            ]
        )
        self.assertTrue(tools)
        self.assertIn("get_sold_storable_products", tools.mapped("name"))

    def test_confirmed_storable_sale_in_frozen_window_is_included(self):
        """A qty-5 confirmed sale at as_of - 10 days is in the envelope."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Frozen Window SKU", "FD-FROZEN-IN")
        order = self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        self._assert_confirmed(order)
        envelope = self._sold_envelope(as_of=FROZEN_AS_OF)
        self.assertIsInstance(envelope, dict)
        self.assertIn("products", envelope)
        self.assertEqual(envelope["as_of"], FROZEN_AS_OF)
        self.assertIn(product.id, [row["id"] for row in envelope["products"]])

    def test_draft_non_storable_zero_qty_or_after_as_of_omitted(self):
        """Draft, non-product, qty 0, and date_order >= as_of are omitted."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        keeper = self._create_product("Frozen Keeper", "FD-FROZEN-KEEP")
        draft = self._create_product("Frozen Draft", "FD-FROZEN-DRAFT")
        consu = self._create_product(
            "Frozen Consu", "FD-FROZEN-CONSU", product_type="consu"
        )
        zero = self._create_product("Frozen Zero", "FD-FROZEN-ZERO")
        after = self._create_product("Frozen After", "FD-FROZEN-AFTER")
        self._create_order([keeper], confirm=True, date_order=in_window, line_qty=5.0)
        self._create_order([draft], confirm=False, date_order=in_window)
        self._create_order([consu], confirm=True, date_order=in_window, line_qty=5.0)
        self._create_order([zero], confirm=True, date_order=in_window, line_qty=0.0)
        self._create_order([after], confirm=True, date_order=as_of, line_qty=5.0)
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertIn(keeper.id, sold_ids)
        self.assertNotIn(draft.id, sold_ids)
        self.assertNotIn(consu.id, sold_ids)
        self.assertNotIn(zero.id, sold_ids)
        self.assertNotIn(after.id, sold_ids)

    def test_later_live_sale_does_not_change_frozen_as_of_replay(self):
        """A sale after as_of must not appear when the same as_of is replayed."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        original = self._create_product("Replay Original", "FD-REPLAY-ORIG")
        later = self._create_product("Replay Later", "FD-REPLAY-LATER")
        self._create_order(
            [original],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        first = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertIn(original.id, first)
        self._create_order(
            [later],
            confirm=True,
            date_order=fields.Datetime.now(),
            line_qty=9.0,
        )
        replay = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertEqual(first, replay)
        self.assertNotIn(later.id, replay)

    def test_coded_sku_is_product_identity(self):
        """Eligible product identity is the trimmed default_code."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Coded SKU", "ABC-1")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertIsNotNone(row)
        self.assertEqual(row["default_code"], "ABC-1")
        self.assertEqual(row["id"], product.id)

    def test_empty_false_whitespace_default_code_excluded(self):
        """Empty, False, and whitespace-only SKUs are omitted."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        coded = self._create_product("Has Code", "FD-HAS-CODE")
        empty = self._create_product("Empty Code", "")
        false_code = self._create_product("False Code", False)
        whitespace = self._create_product("Whitespace Code", "   ")
        self._create_order([coded], confirm=True, date_order=in_window)
        self._create_order([empty], confirm=True, date_order=in_window)
        self._create_order([false_code], confirm=True, date_order=in_window)
        self._create_order([whitespace], confirm=True, date_order=in_window)
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertIn(coded.id, sold_ids)
        self.assertNotIn(empty.id, sold_ids)
        self.assertNotIn(false_code.id, sold_ids)
        self.assertNotIn(whitespace.id, sold_ids)
        codes = [
            row["default_code"]
            for row in self._sold_rows(as_of=FROZEN_AS_OF)
            if row["id"] in (coded.id, empty.id, false_code.id, whitespace.id)
        ]
        self.assertEqual(codes, ["FD-HAS-CODE"])

    def test_envelope_company_id_is_authenticated_company(self):
        """The envelope reports the caller's company; search is not scoped to it."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Company Scope SKU", "FD-CO-A")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        envelope = self._sold_envelope(as_of=FROZEN_AS_OF)
        self.assertEqual(envelope["company_id"], self.env.company.id)

    def test_all_company_orders_and_stock_are_included(self):
        """Orders and quants of every company enter eligibility, demand, and stock."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        company_a = self.env.company
        company_b = self.env["res.company"].create({"name": "Forecast Demand Co B"})
        warehouse_b = self.env["stock.warehouse"].search(
            [("company_id", "=", company_b.id)], limit=1
        )
        self.assertTrue(warehouse_b)
        shared = self._create_product("Shared Co SKU", "FD-CO-SHARED")
        only_b = self._create_product("Only B SKU", "FD-CO-ONLY-B")
        self._create_order(
            [shared],
            confirm=True,
            date_order=in_window,
            line_qty=5.0,
            company=company_a,
        )
        self._create_order(
            [shared],
            confirm=True,
            date_order=in_window,
            line_qty=7.0,
            company=company_b,
            warehouse=warehouse_b,
        )
        self._create_order(
            [only_b],
            confirm=True,
            date_order=in_window,
            line_qty=9.0,
            company=company_b,
            warehouse=warehouse_b,
        )
        self._set_on_hand(
            shared,
            10.0,
            self.warehouse,
            company=company_a,
            move_date=in_window,
        )
        self._set_on_hand(
            shared,
            50.0,
            warehouse_b,
            company=company_b,
            move_date=in_window,
        )
        envelope = self._sold_envelope(as_of=FROZEN_AS_OF, company=company_a)
        self.assertEqual(envelope["company_id"], company_a.id)
        sold_ids = [row["id"] for row in envelope["products"]]
        self.assertIn(shared.id, sold_ids)
        self.assertIn(only_b.id, sold_ids)
        row = self._row_for(shared, as_of=FROZEN_AS_OF, company=company_a)
        self.assertEqual(row["qty_available"], 60.0)
        self.assertEqual(row["periods"][0]["ordered_qty_raw"], 12.0)
        only_b_row = self._row_for(only_b, as_of=FROZEN_AS_OF, company=company_a)
        self.assertEqual(only_b_row["periods"][0]["ordered_qty_raw"], 9.0)

    def test_search_ignores_user_allowed_companies(self):
        """A user limited to company A still sees company B sales and stock."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        company_a = self.env.company
        company_b = self.env["res.company"].create(
            {"name": "Forecast Demand Co B Limited"}
        )
        warehouse_b = self.env["stock.warehouse"].search(
            [("company_id", "=", company_b.id)], limit=1
        )
        self.assertTrue(warehouse_b)
        only_b = self._create_product("User Limited Only B", "FD-CO-USER-B")
        self._create_order(
            [only_b],
            confirm=True,
            date_order=in_window,
            line_qty=9.0,
            company=company_b,
            warehouse=warehouse_b,
        )
        self._set_on_hand(
            only_b,
            50.0,
            warehouse_b,
            company=company_b,
            move_date=in_window,
        )
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Forecast Limited Co User",
                    "login": "forecast_limited_co",
                    "email": "forecast_limited_co@example.com",
                    "company_id": company_a.id,
                    "company_ids": [(6, 0, [company_a.id])],
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("sales_team.group_sale_salesman").id,
                                self.env.ref("stock.group_stock_user").id,
                            ],
                        )
                    ],
                }
            )
        )
        envelope = (
            self.env["product.product"]
            .with_user(user)
            .get_sold_storable_products(as_of=FROZEN_AS_OF, limit=100, offset=0)
        )
        self.assertEqual(envelope["company_id"], company_a.id)
        sold_ids = [row["id"] for row in envelope["products"]]
        self.assertIn(only_b.id, sold_ids)
        row = next(item for item in envelope["products"] if item["id"] == only_b.id)
        self.assertEqual(row["qty_available"], 50.0)
        self.assertEqual(row["periods"][0]["ordered_qty_raw"], 9.0)

    def test_twelve_periods_newest_demand_others_zero(self):
        """Exactly 12 contiguous periods; only period 0 carries newest demand."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Period Newest", "FD-PER-NEW")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        periods = row["periods"]
        self.assertEqual(len(periods), 12)
        self.assertEqual(
            periods[0]["start"],
            fields.Datetime.to_string(as_of - timedelta(days=30)),
        )
        self.assertEqual(periods[0]["end"], FROZEN_AS_OF)
        self.assertEqual(periods[0]["ordered_qty_raw"], 5.0)
        for period in periods[1:]:
            self.assertEqual(period["ordered_qty_raw"], 0.0)
        self.assertEqual(
            periods[11]["start"],
            fields.Datetime.to_string(as_of - timedelta(days=30 * 12)),
        )
        self.assertEqual(
            periods[11]["end"],
            fields.Datetime.to_string(as_of - timedelta(days=30 * 11)),
        )
        for index in range(11):
            self.assertEqual(periods[index + 1]["end"], periods[index]["start"])

    def test_period_bounds_inclusive_start_exclusive_as_of(self):
        """Sale at as_of-30d is period 0; sale at as_of is in none of the 12."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Period Bounds", "FD-PER-BOUNDS")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=30),
            line_qty=3.0,
        )
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of,
            line_qty=4.0,
        )
        older = self._create_product("Period Older", "FD-PER-OLD")
        self._create_order(
            [older],
            confirm=True,
            date_order=as_of - timedelta(days=40),
            line_qty=8.0,
        )
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertEqual(row["periods"][0]["ordered_qty_raw"], 3.0)
        self.assertEqual(
            sum(period["ordered_qty_raw"] for period in row["periods"]), 3.0
        )
        older_row = self._row_for(older, as_of=FROZEN_AS_OF)
        self.assertEqual(older_row["periods"][0]["ordered_qty_raw"], 0.0)
        self.assertEqual(older_row["periods"][1]["ordered_qty_raw"], 8.0)

    def test_older_history_counted_only_for_eligible_sku(self):
        """A 200-day sale is demand history, not eligibility."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        eligible = self._create_product("History Eligible", "FD-HIST-IN")
        too_old = self._create_product("History Only Old", "FD-HIST-OUT")
        self._create_order(
            [eligible],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        self._create_order(
            [eligible],
            confirm=True,
            date_order=as_of - timedelta(days=200),
            line_qty=7.0,
        )
        self._create_order(
            [too_old],
            confirm=True,
            date_order=as_of - timedelta(days=200),
            line_qty=9.0,
        )
        sold_ids = self._sold_ids(as_of=FROZEN_AS_OF)
        self.assertIn(eligible.id, sold_ids)
        self.assertNotIn(too_old.id, sold_ids)
        row = self._row_for(eligible, as_of=FROZEN_AS_OF)
        self.assertEqual(row["periods"][0]["ordered_qty_raw"], 5.0)
        self.assertEqual(row["periods"][6]["ordered_qty_raw"], 7.0)

    def test_sale_older_than_history_window_is_omitted(self):
        """Sales before as_of-360d must not enter the 12 demand buckets."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Beyond History", "FD-HIST-BEYOND")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=5.0,
        )
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=400),
            line_qty=11.0,
        )
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertEqual(row["periods"][0]["ordered_qty_raw"], 5.0)
        self.assertEqual(
            sum(period["ordered_qty_raw"] for period in row["periods"]), 5.0
        )

    def test_live_qty_equals_period_zero_end_stock(self):
        """Live qty_available uses to_date=as_of and matches period-0 end."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of - timedelta(days=10)
        product = self._create_product("ToDate Stock", "FD-TODATE")
        self._create_order(
            [product],
            confirm=True,
            date_order=in_window,
            line_qty=5.0,
        )
        self._set_on_hand(
            product,
            10.0,
            self.warehouse,
            move_date=as_of - timedelta(days=5),
        )
        self._set_on_hand(product, 17.0, self.warehouse)
        company_b = self.env["res.company"].create({"name": "Forecast ToDate Co B"})
        warehouse_b = self.env["stock.warehouse"].search(
            [("company_id", "=", company_b.id)], limit=1
        )
        self.assertTrue(warehouse_b)
        self._set_on_hand(
            product,
            50.0,
            warehouse_b,
            company=company_b,
            move_date=as_of - timedelta(days=5),
        )
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertEqual(row["qty_available"], 60.0)
        self.assertEqual(row["periods"][0]["period_end_qty"], 60.0)
        self.assertEqual(row["qty_available"], row["periods"][0]["period_end_qty"])

    def test_multi_page_shares_frozen_as_of(self):
        """Page 1 freezes as_of; page 2 reuses it; last page has_more is false."""
        as_of_dt = fields.Datetime.to_datetime(FROZEN_AS_OF)
        in_window = as_of_dt - timedelta(days=10)
        products = [
            self._create_product("Page SKU %s" % index, "FD-PAGE-%s" % index)
            for index in (1, 2, 3)
        ]
        for product in products:
            self._create_order(
                [product], confirm=True, date_order=in_window, line_qty=2.0
            )
        frozen_now = as_of_dt
        with patch(
            "odoo.addons.tommasi_forecast_demand.models.product_product.fields.Datetime.now",
            return_value=frozen_now,
        ):
            page1 = self._sold_envelope(limit=2, offset=0)
        self.assertEqual(page1["schema_version"], 1)
        self.assertEqual(page1["as_of"], FROZEN_AS_OF)
        self.assertEqual(page1["company_id"], self.env.company.id)
        self.assertTrue(page1["has_more"])
        self.assertEqual(page1["next_offset"], 2)
        self.assertGreater(page1["next_offset"], 0)
        self.assertEqual(len(page1["products"]), 2)
        page2 = self._sold_envelope(
            as_of=page1["as_of"], limit=2, offset=page1["next_offset"]
        )
        self.assertEqual(page2["schema_version"], 1)
        self.assertEqual(page2["as_of"], page1["as_of"])
        self.assertFalse(page2["has_more"])
        self.assertIsNone(page2["next_offset"])
        self.assertEqual(len(page2["products"]), 1)
        combined = page1["products"] + page2["products"]
        combined_ids = [row["id"] for row in combined]
        self.assertEqual(len(combined_ids), len(set(combined_ids)))
        self.assertEqual(set(combined_ids), {product.id for product in products})

    def test_offset_past_end_returns_empty_page(self):
        """Offset beyond the eligible set yields empty products and has_more false."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        product = self._create_product("Past End SKU", "FD-PAGE-END")
        self._create_order(
            [product],
            confirm=True,
            date_order=as_of - timedelta(days=10),
            line_qty=1.0,
        )
        envelope = self._sold_envelope(as_of=FROZEN_AS_OF, limit=10, offset=50)
        self.assertEqual(envelope["schema_version"], 1)
        self.assertEqual(envelope["as_of"], FROZEN_AS_OF)
        self.assertEqual(envelope["products"], [])
        self.assertFalse(envelope["has_more"])
        self.assertIsNone(envelope["next_offset"])

    def test_alternative_products_empty_when_none(self):
        """Eligible products with no directional alternatives get an empty list."""
        product = self._sold_primary("Alt Empty Primary", "FD-ALT-EMPTY")
        envelope = self._sold_envelope(as_of=FROZEN_AS_OF)
        self.assertEqual(envelope["schema_version"], 1)
        row = self._row_for(product, as_of=FROZEN_AS_OF)
        self.assertIsNotNone(row)
        self.assertEqual(row["alternative_products"], [])

    def test_alternative_products_sums_two_storable_variants(self):
        """One template item sums both active storable variants and sorts SKUs."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt TwoVar Primary", "FD-ALT-2V-PRI")
        alt_tmpl = self._create_template_with_variants(
            "Alt Two Variants",
            {"A": "FD-ALT-SKU-B", "B": "FD-ALT-SKU-A"},
        )
        variant_a = self._variant_for(alt_tmpl, "A")
        variant_b = self._variant_for(alt_tmpl, "B")
        self._set_on_hand(
            variant_a, 4.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._set_on_hand(
            variant_b, 8.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._link_alternative(primary, alt_tmpl)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        self.assertEqual(len(row["alternative_products"]), 1)
        item = row["alternative_products"][0]
        self.assertEqual(
            set(item.keys()),
            {"id", "name", "skus", "qty_available"},
        )
        self.assertEqual(item["id"], alt_tmpl.id)
        self.assertEqual(item["name"], alt_tmpl.name)
        self.assertEqual(item["skus"], ["FD-ALT-SKU-A", "FD-ALT-SKU-B"])
        self.assertEqual(item["qty_available"], 12.0)

    def test_alternative_products_omits_reverse_m2m(self):
        """Reverse-only M2M (alt points at primary) is omitted from the row."""
        primary = self._sold_primary("Alt Reverse Primary", "FD-ALT-REV-PRI")
        other = self._create_product("Alt Reverse Other", "FD-ALT-REV-OTH")
        other.product_tmpl_id.write(
            {"alternative_product_ids": [(4, primary.product_tmpl_id.id)]}
        )
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        self.assertEqual(row["alternative_products"], [])

    def test_alternative_products_skips_primary_template(self):
        """The primary template listed as its own alternative is skipped."""
        primary = self._sold_primary("Alt Self Primary", "FD-ALT-SELF-PRI")
        self._link_alternative(primary, primary.product_tmpl_id)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        self.assertEqual(row["alternative_products"], [])

    def test_alternative_products_dedupes_duplicate_m2m(self):
        """Duplicate M2M rows for the same template yield one list item."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt Dedupe Primary", "FD-ALT-DED-PRI")
        alt_tmpl = self._create_template_with_variants(
            "Alt Dedupe Tmpl", {"X": "FD-ALT-DED-SKU"}
        )
        variant = self._variant_for(alt_tmpl, "X")
        self._set_on_hand(
            variant, 3.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._link_alternative(primary, alt_tmpl)
        # Rel table PK forbids a second SQL row; seed a duplicated id tuple
        # in the M2M cache so the helper still sees T twice.
        field = primary.product_tmpl_id._fields["alternative_product_ids"]
        self.env.cache.set(
            primary.product_tmpl_id, field, (alt_tmpl.id, alt_tmpl.id)
        )
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        matching = [
            item
            for item in row["alternative_products"]
            if item["id"] == alt_tmpl.id
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["skus"], ["FD-ALT-DED-SKU"])
        self.assertEqual(matching[0]["qty_available"], 3.0)

    def test_alternative_products_sku_less_variant_counts_qty(self):
        """SKU-less active storable variants add qty but omit empty codes."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt Skuless Primary", "FD-ALT-SKL-PRI")
        alt_tmpl = self._create_template_with_variants(
            "Alt Skuless Tmpl",
            {"Coded": "FD-ALT-SKL-CODE", "Bare": ""},
        )
        coded = self._variant_for(alt_tmpl, "Coded")
        bare = self._variant_for(alt_tmpl, "Bare")
        self._set_on_hand(
            coded, 2.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._set_on_hand(
            bare, 3.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._link_alternative(primary, alt_tmpl)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        item = row["alternative_products"][0]
        self.assertEqual(item["qty_available"], 5.0)
        self.assertEqual(item["skus"], ["FD-ALT-SKL-CODE"])
        self.assertNotIn("", item["skus"])

    def test_alternative_products_ignores_inactive_and_non_storable(self):
        """Inactive storable and active non-storable variants are ignored."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt Skip Primary", "FD-ALT-SKIP-PRI")
        storable_tmpl = self._create_template_with_variants(
            "Alt Skip Storable",
            {"Keep": "FD-ALT-SKIP-KEEP", "Dead": "FD-ALT-SKIP-DEAD"},
        )
        keep = self._variant_for(storable_tmpl, "Keep")
        dead = self._variant_for(storable_tmpl, "Dead")
        self._set_on_hand(
            keep, 4.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._set_on_hand(
            dead, 8.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        dead.active = False
        service = self._create_product(
            "Alt Skip Service", "FD-ALT-SKIP-SERV", product_type="service"
        )
        self._link_alternative(primary, storable_tmpl)
        self._link_alternative(primary, service.product_tmpl_id)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        by_id = {item["id"]: item for item in row["alternative_products"]}
        self.assertIn(storable_tmpl.id, by_id)
        storable_item = by_id[storable_tmpl.id]
        self.assertEqual(storable_item["skus"], ["FD-ALT-SKIP-KEEP"])
        self.assertNotIn("FD-ALT-SKIP-DEAD", storable_item["skus"])
        self.assertEqual(storable_item["qty_available"], 4.0)
        self.assertNotIn(service.product_tmpl_id.id, by_id)

    def test_alternative_products_omits_zero_qty(self):
        """Directional alternatives with zero frozen on-hand are omitted."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt Zero Primary", "FD-ALT-ZERO-PRI")
        zero_tmpl = self._create_template_with_variants(
            "Alt Zero Tmpl", {"X": "FD-ALT-ZERO-SKU"}
        )
        kept_tmpl = self._create_template_with_variants(
            "Alt Kept Tmpl", {"Y": "FD-ALT-KEPT-SKU"}
        )
        kept = self._variant_for(kept_tmpl, "Y")
        self._set_on_hand(
            kept, 5.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        self._link_alternative(primary, zero_tmpl)
        self._link_alternative(primary, kept_tmpl)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        by_id = {item["id"]: item for item in row["alternative_products"]}
        self.assertNotIn(zero_tmpl.id, by_id)
        self.assertIn(kept_tmpl.id, by_id)
        self.assertEqual(by_id[kept_tmpl.id]["qty_available"], 5.0)
        self.assertEqual(by_id[kept_tmpl.id]["skus"], ["FD-ALT-KEPT-SKU"])

    def test_alternative_products_qty_uses_frozen_as_of(self):
        """On-hand counted after as_of must not appear on alternative qty."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        primary = self._sold_primary("Alt Frozen Primary", "FD-ALT-FRZ-PRI")
        alt_tmpl = self._create_template_with_variants(
            "Alt Frozen Tmpl", {"X": "FD-ALT-FRZ-SKU"}
        )
        variant = self._variant_for(alt_tmpl, "X")
        self._set_on_hand(
            variant,
            10.0,
            self.warehouse,
            move_date=as_of - timedelta(days=5),
        )
        self._set_on_hand(variant, 17.0, self.warehouse)
        self._link_alternative(primary, alt_tmpl)
        row = self._row_for(primary, as_of=FROZEN_AS_OF)
        item = row["alternative_products"][0]
        self.assertEqual(item["qty_available"], 10.0)

    def test_alternative_products_qty_is_batched_per_page(self):
        """Alternative on-hand uses one extra _qty_available_at, not one per row."""
        as_of = fields.Datetime.to_datetime(FROZEN_AS_OF)
        alt_tmpl = self._create_template_with_variants(
            "Alt Batch Tmpl", {"X": "FD-ALT-BAT-SKU"}
        )
        alt_variant = self._variant_for(alt_tmpl, "X")
        self._set_on_hand(
            alt_variant, 6.0, self.warehouse, move_date=as_of - timedelta(days=5)
        )
        primaries = [
            self._sold_primary(
                "Alt Batch Primary %s" % index, "FD-ALT-BAT-%s" % index
            )
            for index in (1, 2, 3)
        ]
        for primary in primaries:
            self._link_alternative(primary, alt_tmpl)
        ProductProduct = type(self.env["product.product"])
        real_qty = ProductProduct._qty_available_at
        calls = []

        def _spy(this, products, when, company_ids):
            calls.append(list(products.ids))
            return real_qty(this, products, when, company_ids)

        with patch.object(ProductProduct, "_qty_available_at", _spy):
            envelope = self._sold_envelope(as_of=FROZEN_AS_OF)
        alt_ids = set(alt_tmpl.product_variant_ids.ids)
        alt_calls = [ids for ids in calls if alt_ids.intersection(ids)]
        self.assertEqual(len(alt_calls), 1)
        self.assertEqual(len(primaries), 3)
        sold_ids = {row["id"] for row in envelope["products"]}
        self.assertTrue(sold_ids.issuperset({primary.id for primary in primaries}))
