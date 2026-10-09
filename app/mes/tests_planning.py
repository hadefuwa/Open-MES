from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from .models import CustomerOrder, CustomerOrderLine, Product, ProductionTechnician, WorkOrder
from .views_planning import order_state

TODAY = date.today()


def day(n):
    return TODAY + timedelta(days=n)


class PlanningTimelineTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(code="FG1000", name="Test unit", kind=Product.FINISHED)
        cls.tech = ProductionTechnician.objects.create(name="Alex")
        make = WorkOrder.objects.create
        cls.overdue = make(number="9001", product=cls.product, quantity=3, start_date=day(-8), due_date=day(-2),
                           status=WorkOrder.IN_PROGRESS, technician=cls.tech)
        cls.future = make(number="9002", product=cls.product, quantity=2, start_date=day(3), due_date=day(9),
                          status=WorkOrder.ENTERED)
        cls.no_start = make(number="9003", product=cls.product, quantity=1, due_date=day(5), status=WorkOrder.ALLOCATED)
        cls.no_due = make(number="9004", product=cls.product, quantity=1, status=WorkOrder.ENTERED)
        cls.done = make(number="9005", product=cls.product, quantity=1, start_date=day(-5), due_date=day(-4),
                        status=WorkOrder.COMPLETE)

        cls.late_order = CustomerOrder.objects.create(
            number="29001", order_date=day(-10), ship_date=day(-3), customer="Test College")
        CustomerOrderLine.objects.create(order=cls.late_order, product=cls.product, quantity=3, work_order=cls.overdue)
        cls.shipped_order = CustomerOrder.objects.create(
            number="29002", order_date=day(-10), ship_date=day(-3), customer="Other College")
        CustomerOrderLine.objects.create(order=cls.shipped_order, product=cls.product, quantity=1, work_order=cls.done)
        cls.unplanned_order = CustomerOrder.objects.create(
            number="29003", order_date=day(-1), ship_date=day(12), customer="Third College")
        CustomerOrderLine.objects.create(order=cls.unplanned_order, product=cls.product, quantity=2)

    def get(self, **params):
        return self.client.get(reverse("timeline"), params)

    def test_renders_with_and_without_filters(self):
        self.assertEqual(self.get().status_code, 200)
        response = self.get(product=self.product.pk, tech=self.tech.pk, status="in_progress", weeks=12, shift=1)
        self.assertEqual(response.status_code, 200)
        self.assertContains(self.get(status="all"), "9005")
        self.assertEqual(self.get(product="abc", weeks="x", shift="y", status="nope").status_code, 200)

    def test_default_hides_complete_orders(self):
        content = self.get().content.decode()
        self.assertIn("9001", content)
        self.assertNotIn("9005", content)

    def test_overdue_and_late_detection(self):
        self.assertTrue(self.overdue.is_overdue)
        self.assertEqual(order_state(self.late_order, TODAY)[2], True)
        self.assertEqual(order_state(self.shipped_order, TODAY)[0], "Shipped")
        self.assertEqual(order_state(self.unplanned_order, TODAY)[0], "No works order")
        kpi = self.get().context["kpi"]
        self.assertEqual(kpi["overdue"], 1)
        self.assertEqual(kpi["ship_late"], 1)

    def test_bars_and_markers_link_to_detail_pages(self):
        content = self.get().content.decode()
        self.assertIn(f'href="{reverse("operator", args=[self.overdue.pk])}"', content)
        self.assertIn(f'href="{reverse("customer_order", args=[self.late_order.pk])}"', content)
        self.assertIn("tl-bar", content)
        self.assertIn("Overdue", content)

    def test_orders_without_start_or_due_date(self):
        response = self.get()
        self.assertContains(response, "no start date")
        self.assertContains(response, "Not scheduled")
        self.assertContains(response, "9004")

    def test_filters_narrow_the_chart(self):
        content = self.get(tech=self.tech.pk).content.decode()
        self.assertIn("9001", content)
        self.assertNotIn("9002", content)

    def test_csv_export(self):
        response = self.get(format="csv", status="all")
        self.assertEqual(response["Content-Type"], "text/csv")
        text = response.content.decode()
        self.assertIn("Type,Number", text.splitlines()[0])
        self.assertIn("Build,9001", text)
        self.assertIn("Ship,29001", text)
        self.assertIn("Updated", text.splitlines()[0])
