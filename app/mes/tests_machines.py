from datetime import date

from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from .models import BomLine, Machine, Product, RoutingStep, WorkOrder
from .views_machines import machine_impact


class MachineFixture(TestCase):
    def setUp(self):
        self.oven = Machine.objects.create(name="Oven", kind="Heat", status=Machine.DOWN, location="Bay 1")
        self.rig = Machine.objects.create(name="Rig", kind="Test")
        self.board = Product.objects.create(code="AU1", name="Board", kind=Product.ASSEMBLY)
        self.unit = Product.objects.create(code="FP1", name="Unit", kind=Product.FINISHED)
        self.other = Product.objects.create(code="FP2", name="Other", kind=Product.FINISHED)
        BomLine.objects.create(parent=self.unit, child=self.board, quantity=1)
        RoutingStep.objects.create(product=self.board, sequence=10, name="Reflow", machine=self.oven, minutes=10)
        RoutingStep.objects.create(product=self.other, sequence=10, name="Test", machine=self.rig, minutes=5)
        RoutingStep.objects.create(product=self.other, sequence=20, name="Pack", minutes=2)
        self.open_wo = WorkOrder.objects.create(number="1", product=self.unit, quantity=1, due_date=date.today())
        WorkOrder.objects.create(number="2", product=self.unit, quantity=1, status=WorkOrder.COMPLETE)
        WorkOrder.objects.create(number="3", product=self.other, quantity=1)


class MachineViewTests(MachineFixture):
    def test_list_renders(self):
        r = self.client.get(reverse("machines"))
        self.assertContains(r, "Oven")
        self.assertContains(r, "Down")
        self.assertEqual(r.context["counts"]["down"], 1)

    def test_list_csv(self):
        r = self.client.get(reverse("machines"), {"format": "csv"})
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn("Oven", r.content.decode())

    def test_detail_renders_with_banner(self):
        r = self.client.get(reverse("machine_detail", args=[self.oven.pk]))
        self.assertContains(r, "1 finished product and 1 open work order impacted")
        self.assertContains(r, "Finished products affected")

    def test_detail_csv(self):
        r = self.client.get(reverse("machine_detail", args=[self.oven.pk]), {"format": "csv"})
        self.assertIn("AU1", r.content.decode())

    def test_available_machine_has_no_banner(self):
        r = self.client.get(reverse("machine_detail", args=[self.rig.pk]))
        self.assertNotContains(r, "impacted")

    def test_status_change(self):
        url = reverse("machine_status", args=[self.oven.pk])
        r = self.client.post(url, {"status": "available"})
        self.assertRedirects(r, reverse("machine_detail", args=[self.oven.pk]))
        self.oven.refresh_from_db()
        self.assertEqual(self.oven.status, Machine.AVAILABLE)

    def test_invalid_status_rejected(self):
        r = self.client.post(reverse("machine_status", args=[self.oven.pk]), {"status": "exploded"})
        self.assertEqual(r.status_code, 400)
        self.oven.refresh_from_db()
        self.assertEqual(self.oven.status, Machine.DOWN)

    def test_get_does_not_change(self):
        r = self.client.get(reverse("machine_status", args=[self.oven.pk]), {"status": "available"})
        self.assertEqual(r.status_code, 405)
        self.oven.refresh_from_db()
        self.assertEqual(self.oven.status, Machine.DOWN)


class ImpactTests(MachineFixture):
    def test_impact_through_assembly(self):
        direct, finished, orders = machine_impact(self.oven)
        self.assertEqual(direct, {self.board.pk})
        self.assertEqual([p.code for p in finished], ["FP1"])
        self.assertEqual([o.number for o in orders], ["1"])

    def test_direct_finished_product(self):
        direct, finished, orders = machine_impact(self.rig)
        self.assertEqual([p.code for p in finished], ["FP2"])
        self.assertEqual([o.number for o in orders], ["3"])


class ProductPanelTests(MachineFixture):
    def render(self, product):
        tpl = Template('{% include "mes/machines/_product_panel.html" %}')
        return tpl.render(Context({"product": product}))

    def test_panel_with_routing(self):
        html = self.render(self.board)
        self.assertIn("Routing", html)
        self.assertIn("Oven", html)
        self.assertIn("Machine not available", html)

    def test_panel_manual_step_and_total(self):
        html = self.render(self.other)
        self.assertIn("Manual (no machine)", html)
        self.assertNotIn("Machine not available", html)
        self.assertIn("<strong>7</strong>", html)

    def test_panel_empty_without_routing(self):
        self.assertNotIn("Routing", self.render(self.unit))
