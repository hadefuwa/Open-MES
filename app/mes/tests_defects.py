from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import BomLine, Defect, Event, Product, ProductionTechnician, Unit, WorkOrder


class DefectsTestBase(TestCase):
    def setUp(self):
        self.finished = Product.objects.create(code="FIN1", name="Finished thing", kind=Product.FINISHED)
        self.sub = Product.objects.create(code="SUB1", name="Sub assembly", kind=Product.ASSEMBLY)
        self.screw = Product.objects.create(code="SCR1", name="Screw", kind=Product.COMPONENT,
                                            unit_cost=Decimal("0.25"))
        self.pcb = Product.objects.create(code="PCB1", name="Circuit board", kind=Product.COMPONENT,
                                          unit_cost=Decimal("4.50"))
        BomLine.objects.create(parent=self.finished, child=self.sub, quantity=1)
        BomLine.objects.create(parent=self.sub, child=self.screw, quantity=4)
        BomLine.objects.create(parent=self.finished, child=self.pcb, quantity=1)
        self.tech = ProductionTechnician.objects.create(name="Alex")
        self.order = WorkOrder.objects.create(
            number="9001", product=self.finished, quantity=5, due_date=date.today(),
            status=WorkOrder.IN_PROGRESS, technician=self.tech)
        self.unit = Unit.objects.create(work_order=self.order, serial="FIN1-0001", result=Unit.PASS)

    def add(self, **data):
        return self.client.post(reverse("defect_add", args=[self.order.pk]), data)


class DefectsPageTest(DefectsTestBase):
    def setUp(self):
        super().setUp()
        Defect.objects.create(product=self.finished, component=self.screw, work_order=self.order,
                              unit=self.unit, quantity=3, unit_cost=Decimal("0.25"),
                              description="Wrong screw fitted", reported_by=self.tech)
        Defect.objects.create(product=self.finished, work_order=self.order, quantity=1,
                              unit_cost=Decimal("20.00"), description="Cracked housing")

    def test_list_renders(self):
        r = self.client.get(reverse("defects"))
        self.assertContains(r, "Wrong screw fitted")
        self.assertContains(r, "Whole unit")
        self.assertContains(r, "Defects this month")
        self.assertContains(r, reverse("operator", args=[self.order.pk]))
        self.assertContains(r, "?serial=FIN1-0001")

    def test_search_filters(self):
        r = self.client.get(reverse("defects"), {"q": "SCR1"})
        self.assertContains(r, "Wrong screw fitted")
        self.assertContains(r, "1 row")

    def test_csv_export(self):
        r = self.client.get(reverse("defects"), {"format": "csv"})
        self.assertEqual(r["Content-Type"], "text/csv")
        body = r.content.decode()
        self.assertIn("Total cost", body)
        self.assertIn("0.75", body)
        self.assertIn("20.00", body)

    def test_empty_page_renders(self):
        Defect.objects.all().delete()
        self.assertEqual(self.client.get(reverse("defects")).status_code, 200)


class DefectAddTest(DefectsTestBase):
    def test_component_defect_uses_part_cost(self):
        r = self.add(component=self.screw.pk, quantity="6", description="Stripped thread",
                     serial="FIN1-0001", reported_by=self.tech.pk)
        self.assertRedirects(r, f"/operator/{self.order.pk}/?notice=Defect%20recorded%3A%206%20x%20SCR1%2C%20cost%20%C2%A31.50",
                             fetch_redirect_response=False)
        d = Defect.objects.get()
        self.assertEqual((d.component, d.unit_cost, d.quantity, d.cost), (self.screw, Decimal("0.25"), 6, Decimal("1.50")))
        self.assertEqual(d.product, self.finished)
        self.assertEqual(d.unit, self.unit)
        self.assertEqual(d.reported_by, self.tech)
        self.assertTrue(Event.objects.filter(work_order=self.order, action="defect recorded").exists())

    def test_whole_unit_uses_total_cost(self):
        self.add(component="whole", quantity="1", description="Scrapped in test")
        d = Defect.objects.get()
        self.assertIsNone(d.component)
        self.assertEqual(d.unit_cost, Decimal("5.50"))

    def test_rejects_bad_input(self):
        other = Product.objects.create(code="OTH", name="Not in BOM", kind=Product.COMPONENT)
        for data in (
            {"component": self.screw.pk, "quantity": "0", "description": "x"},
            {"component": self.screw.pk, "quantity": "abc", "description": "x"},
            {"component": self.screw.pk, "quantity": "1", "description": " "},
            {"component": "", "quantity": "1", "description": "x"},
            {"component": other.pk, "quantity": "1", "description": "x"},
            {"component": self.screw.pk, "quantity": "1", "description": "x", "serial": "NOPE"},
            {"component": self.screw.pk, "quantity": "1", "description": "x", "reported_by": "999"},
        ):
            r = self.add(**data)
            self.assertIn("error=", r["Location"], data)
        self.assertEqual(Defect.objects.count(), 0)

    def test_get_not_allowed_and_status_checked(self):
        self.assertEqual(self.client.get(reverse("defect_add", args=[self.order.pk])).status_code, 405)
        self.order.status = WorkOrder.ENTERED
        self.order.save()
        self.assertIn("error=", self.add(component="whole", quantity="1", description="x")["Location"])
        self.assertEqual(Defect.objects.count(), 0)

    def test_operator_page_shows_form_with_flattened_parts(self):
        r = self.client.get(reverse("operator", args=[self.order.pk]))
        self.assertContains(r, "Record a defect")
        self.assertContains(r, "SCR1")
        self.assertContains(r, "PCB1")
        self.order.status = WorkOrder.ISSUED
        self.order.save()
        self.assertNotContains(self.client.get(reverse("operator", args=[self.order.pk])), "Record a defect")


class ScrapDefectTest(DefectsTestBase):
    def test_scrap_on_add_creates_one_defect(self):
        self.client.post(reverse("add_unit", args=[self.order.pk]),
                         {"serial": "FIN1-0002", "result": "scrap", "reason": "Burnt board"})
        d = Defect.objects.get()
        self.assertEqual((d.description, d.quantity, d.unit_cost), ("Burnt board", 1, Decimal("5.50")))
        self.assertIsNone(d.component)
        self.assertEqual(d.unit.serial, "FIN1-0002")
        self.assertEqual(d.work_order, self.order)
        self.assertEqual(d.reported_by, self.tech)

    def test_retest_scrap_creates_defect_once(self):
        unit = Unit.objects.create(work_order=self.order, serial="FIN1-0003", result=Unit.REWORK,
                                   reason="Loose joint", first_pass=False)
        url = reverse("retest_unit", args=[self.order.pk, unit.pk])
        self.client.post(url, {"result": "scrap"})
        self.client.post(url, {"result": "scrap"})
        self.assertEqual(Defect.objects.filter(unit=unit).count(), 1)

    def test_pass_creates_no_defect(self):
        self.client.post(reverse("add_unit", args=[self.order.pk]), {"serial": "X1", "result": "pass"})
        self.assertEqual(Defect.objects.count(), 0)


class DashboardAndPanelTest(DefectsTestBase):
    def test_dashboard_shows_defects_tile(self):
        Defect.objects.create(product=self.finished, quantity=2, unit_cost=Decimal("10.00"), description="x")
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Defects this month")
        self.assertContains(r, "20.00")
        self.assertContains(r, "Cost of defects by week")
        self.assertEqual(len(r.context["chart_data"]["defectWeeks"]), 8)

    def test_dashboard_without_defects(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_product_panel(self):
        url = self.screw.get_absolute_url()
        self.assertNotContains(self.client.get(url), "View all defects")
        Defect.objects.create(product=self.finished, component=self.screw, quantity=2,
                              unit_cost=Decimal("0.25"), description="Bent leg")
        r = self.client.get(url)
        self.assertContains(r, "View all defects")
        self.assertContains(r, "Bent leg")
        self.assertContains(self.client.get(self.finished.get_absolute_url()), "Bent leg")
