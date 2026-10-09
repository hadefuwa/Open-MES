import os
import tempfile
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from . import costing, pricing
from .models import BomLine, Product, RoutingStep


def make_workbook(path):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Other"
    ws = wb.create_sheet("Prices")
    ws.append(["Customer pricelist"])  # title row is ignored
    ws.append(["Renewables"])  # section heading
    ws.append(["XX1000", "Wind trainer", 900])
    ws.append(["XX2000", "Solar trainer", 600])
    ws.append(["XX2000", "Duplicate row is ignored", 999])
    ws.append(["Fundamental Mechanics"])
    ws.append(["YY1000", "Statics kit", 300])
    wb.save(path)


class PricingTest(TestCase):
    def setUp(self):
        self.part = Product.objects.create(code="COM1", name="Part", kind=Product.COMPONENT, unit_cost=Decimal("10"))
        self.built = Product.objects.create(code="XX1000", name="Old name", kind=Product.FINISHED)
        BomLine.objects.create(parent=self.built, child=self.part, quantity=5)  # 50.00 of itemised parts
        self.cheap = Product.objects.create(code="YY1000", name="Cheap", kind=Product.FINISHED)
        BomLine.objects.create(parent=self.cheap, child=self.part, quantity=5)  # 50.00 > 300/3? no: 100
        self.unpriced = Product.objects.create(code="ZZ1", name="No price", kind=Product.FINISHED)
        BomLine.objects.create(parent=self.unpriced, child=self.part, quantity=2)
        RoutingStep.objects.create(product=self.unpriced, name="Build", minutes=60)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "prices.xlsx")
            make_workbook(path)
            self.created, self.updated = pricing.import_price_list(path)
        self.stats = pricing.calibrate_costs()

    def test_import_updates_existing_and_creates_new(self):
        self.assertEqual((self.created, self.updated), (1, 2))  # XX2000 new; XX1000 and YY1000 updated
        built = Product.objects.get(code="XX1000")
        self.assertEqual((built.rrp, built.name, built.range_name), (Decimal("900"), "Wind trainer", "Renewables"))
        new = Product.objects.get(code="XX2000")
        self.assertEqual((new.rrp, new.unit_cost, new.kind), (Decimal("600"), Decimal("200.00"), Product.FINISHED))
        self.assertEqual(Product.objects.filter(code="XX2000").count(), 1)  # duplicate row ignored

    def test_bom_cost_is_a_third_of_rrp(self):
        self.assertEqual(costing.bom_cost(Product.objects.get(code="XX1000")), Decimal("300.00"))
        self.assertEqual(costing.bom_cost(Product.objects.get(code="YY1000")), Decimal("100.00"))
        self.assertEqual(costing.bom_cost(Product.objects.get(code="XX2000")), Decimal("200.00"))  # no BOM: unit cost

    def test_top_up_line_is_transparent_and_idempotent(self):
        other = Product.objects.get(code=pricing.OTHER_MATERIALS_CODE)
        self.assertEqual(BomLine.objects.get(parent=self.built, child=other).quantity, Decimal("250.00"))
        pricing.calibrate_costs()  # running again must not stack a second line
        self.assertEqual(BomLine.objects.filter(parent=self.built, child=other).count(), 1)
        self.assertEqual(costing.bom_cost(Product.objects.get(code="XX1000")), Decimal("300.00"))

    def test_unpriced_product_gets_flagged_estimate_that_covers_labour(self):
        p = Product.objects.get(code="ZZ1")
        self.assertTrue(p.rrp_estimated)
        self.assertGreaterEqual(p.rrp, p.total_cost * Decimal("2.5") - 5)
        self.assertGreater(p.margin_pct, 50)

    def test_products_page_shows_rrp_margin_and_range_filter(self):
        resp = self.client.get(reverse("products"))
        self.assertContains(resp, "Wind trainer")
        self.assertContains(resp, "Margin")
        filtered = self.client.get(reverse("products"), {"range": "Renewables"})
        codes = [row[0].text for row in filtered.context["table"].rows]
        self.assertEqual(sorted(codes), ["XX1000", "XX2000"])
        detail = self.client.get(reverse("product_detail", args=[Product.objects.get(code="XX1000").pk]))
        self.assertContains(detail, "£900.00")
