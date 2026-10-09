from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import BomLine, CustomerOrder, CustomerOrderLine, Product, WorkOrder


class TraceabilityPolishTest(TestCase):
    def setUp(self):
        self.finished = Product.objects.create(code="FG1000", name="Finished", kind=Product.FINISHED)
        self.part = Product.objects.create(code="COM1000", name="Part", kind=Product.COMPONENT, unit_cost=2)
        BomLine.objects.create(parent=self.finished, child=self.part, quantity=3)
        self.order = WorkOrder.objects.create(number="9001", product=self.finished, quantity=2,
                                              due_date=date.today())
        co = CustomerOrder.objects.create(number="C9", order_date=date.today(), customer="Test Co")
        CustomerOrderLine.objects.create(order=co, product=self.finished, quantity=2, work_order=self.order)

    def test_data_browser_lists_every_table_with_counts(self):
        resp = self.client.get(reverse("data_browser"))
        self.assertEqual(resp.status_code, 200)
        names = {t["name"]: t for t in resp.context["tables"]}
        self.assertEqual(names["Product"]["rows"], 2)
        self.assertEqual(names["BomLine"]["rows"], 1)
        self.assertIn("Product", [r["name"] for r in names["BomLine"]["relations"]])
        self.assertGreater(resp.context["total_links"], 10)

    def test_data_table_shows_rows_links_and_csv(self):
        resp = self.client.get(reverse("data_table", args=["bomline"]))
        self.assertContains(resp, "COM1000")
        self.assertContains(resp, self.part.get_absolute_url())  # foreign keys are links
        csv_resp = self.client.get(reverse("data_table", args=["product"]), {"format": "csv"})
        self.assertEqual(csv_resp["Content-Type"], "text/csv")
        self.assertIn("COM1000", csv_resp.content.decode())
        self.assertEqual(self.client.get(reverse("data_table", args=["nonsense"])).status_code, 404)

    def test_breadcrumbs_trace_the_path(self):
        resp = self.client.get(reverse("bom", args=[self.finished.pk]))
        labels = [label for label, _ in resp.context["breadcrumbs"]]
        self.assertEqual(labels, ["Dashboard", "Catalogue", "Products", "FG1000", "Bill of materials"])
        resp = self.client.get(reverse("operator", args=[self.order.pk]))
        self.assertEqual(resp.context["breadcrumbs"][-1][0], "Work order 9001")
        self.assertEqual(self.client.get(reverse("dashboard")).context["breadcrumbs"], [])

    def test_work_order_page_links_related_records(self):
        resp = self.client.get(reverse("operator", args=[self.order.pk]))
        self.assertContains(resp, self.finished.get_absolute_url())
        self.assertContains(resp, reverse("bom", args=[self.finished.pk]))
        self.assertContains(resp, reverse("customer_order", args=[CustomerOrder.objects.get().pk]))
