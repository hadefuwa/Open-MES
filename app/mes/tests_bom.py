from decimal import Decimal

from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from . import bom, costing
from .models import BomLine, Product, RoutingStep


def D(x):
    return Decimal(str(x))


class BomFixture(TestCase):
    """FIN = 2 x ASM + 1 x C1 ; ASM = 3 x C2 + 4 x C1 ; C1 = 1.50, C2 = 2.00."""

    @classmethod
    def setUpTestData(cls):
        cls.c1 = Product.objects.create(code="COM9001", name="Resistor", kind="component", unit_cost=D("1.50"))
        cls.c2 = Product.objects.create(code="COM9002", name="Capacitor", kind="component", unit_cost=D("2.00"))
        cls.asm = Product.objects.create(code="SA9100", name="Sub board", kind="assembly")
        cls.fin = Product.objects.create(code="FG9200", name="Finished unit", kind="finished")
        BomLine.objects.create(parent=cls.asm, child=cls.c2, quantity=3, sequence=1)
        BomLine.objects.create(parent=cls.asm, child=cls.c1, quantity=4, sequence=2)
        BomLine.objects.create(parent=cls.fin, child=cls.asm, quantity=2, sequence=1)
        BomLine.objects.create(parent=cls.fin, child=cls.c1, quantity=1, sequence=2)
        RoutingStep.objects.create(product=cls.asm, sequence=1, name="Solder", minutes=D("6"))
        RoutingStep.objects.create(product=cls.fin, sequence=1, name="Final", minutes=D("10"))


class ExplodeTests(BomFixture):
    def test_explosion_quantities_and_costs(self):
        rows = bom.explode(self.fin)
        by_code = {(r.level, r.child.code): r for r in rows}
        self.assertEqual(len(rows), 4)
        asm = by_code[(0, "SA9100")]
        self.assertEqual(asm.ext_quantity, 2)
        self.assertEqual(asm.unit_cost, D("12.00"))          # 3*2.00 + 4*1.50
        self.assertEqual(asm.ext_cost, D("24.00"))
        self.assertTrue(asm.is_assembly)
        self.assertEqual(by_code[(1, "COM9002")].ext_quantity, 6)
        self.assertEqual(by_code[(1, "COM9002")].ext_cost, D("12.00"))
        self.assertEqual(by_code[(1, "COM9001")].ext_quantity, 8)
        self.assertEqual(by_code[(0, "COM9001")].ext_quantity, 1)
        self.assertEqual(asm.minutes, 6)

    def test_bom_cost_matches_costing(self):
        self.assertEqual(self.fin.bom_cost, D("25.50"))
        top = sum(r.ext_cost for r in bom.explode(self.fin) if r.level == 0)
        self.assertEqual(top, costing.bom_cost(self.fin))

    def test_flat_components_aggregate(self):
        flat = {f.product.code: f for f in bom.flat_components(self.fin)}
        self.assertEqual(set(flat), {"COM9001", "COM9002"})
        self.assertEqual(flat["COM9001"].quantity, 9)
        self.assertEqual(flat["COM9001"].cost, D("13.50"))
        self.assertEqual(flat["COM9002"].quantity, 6)
        self.assertEqual(sum(f.cost for f in flat.values()), costing.bom_cost(self.fin))

    def test_where_used(self):
        direct = bom.where_used_direct(self.c1)
        self.assertEqual({l.parent.code for l in direct}, {"SA9100", "FG9200"})
        everywhere = {w.product.code: w for w in bom.where_used_all(self.c2)}
        self.assertEqual(set(everywhere), {"SA9100", "FG9200"})
        self.assertTrue(everywhere["FG9200"].is_finished)
        self.assertEqual(everywhere["FG9200"].quantity, 6)
        self.assertEqual([p.code for p in everywhere["FG9200"].paths[0]], ["FG9200", "SA9100", "COM9002"])
        c1 = {w.product.code: w for w in bom.where_used_all(self.c1)}
        self.assertEqual(c1["FG9200"].quantity, 9)
        self.assertEqual(len(c1["FG9200"].paths), 2)

    def test_cycle_rejected(self):
        with self.assertRaises(ValidationError):
            BomLine.objects.create(parent=self.asm, child=self.fin, quantity=1)
        with self.assertRaises(ValidationError):
            BomLine.objects.create(parent=self.asm, child=self.asm, quantity=1)


class BomPageTests(BomFixture):
    def test_pages_render(self):
        r = self.client.get(reverse("bom", args=[self.fin.pk]))
        self.assertContains(r, "SA9100")
        self.assertContains(r, reverse("component_detail", args=[self.c1.pk]))
        self.assertContains(r, reverse("bom", args=[self.asm.pk]))
        self.assertContains(r, "25.50")
        self.assertEqual(self.client.get(reverse("bom", args=[self.c1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("bom", args=[self.fin.pk]) + "?view=flat").status_code, 200)
        r = self.client.get(reverse("component_detail", args=[self.c1.pk]))
        self.assertContains(r, "FG9200")
        self.assertContains(r, "SA9100")

    def test_csv_exports(self):
        r = self.client.get(reverse("bom", args=[self.fin.pk]) + "?format=csv")
        self.assertEqual(r["Content-Type"], "text/csv")
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(len(lines), 5)
        self.assertIn("SA9100", lines[1])
        r = self.client.get(reverse("bom", args=[self.fin.pk]) + "?view=flat&format=csv")
        self.assertIn("COM9001", r.content.decode())
        r = self.client.get(reverse("component_detail", args=[self.c1.pk]) + "?format=csv")
        self.assertIn("FG9200", r.content.decode())

    def test_panel_renders_for_each_kind(self):
        tpl = Template('{% include "mes/bom/_product_panel.html" %}')
        comp = tpl.render(Context({"product": self.c1}))
        self.assertIn("Where used", comp)
        self.assertNotIn("Bill of materials", comp)
        assembly = tpl.render(Context({"product": self.asm}))
        self.assertIn("Bill of materials", assembly)
        self.assertIn("View full BOM", assembly)
        self.assertIn("Where used", assembly)
        finished = tpl.render(Context({"product": self.fin}))
        self.assertIn("COM9001", finished)
        self.assertNotIn("Where used", finished)
