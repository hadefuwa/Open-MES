from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import BomLine, CustomerOrder, CustomerOrderLine, Product, Unit, WorkOrder


class CatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.finished = Product.objects.create(code="FG1000", name="Smart Thing", kind=Product.FINISHED)
        cls.assembly = Product.objects.create(code="SA2000", name="Gantry", kind=Product.ASSEMBLY)
        cls.com1 = Product.objects.create(code="COM1", name="Motor", kind=Product.COMPONENT,
                                          unit_cost=Decimal("5.00"))
        cls.fix1 = Product.objects.create(code="FIX1", name="Bracket", kind=Product.COMPONENT,
                                          unit_cost=Decimal("1.00"))
        BomLine.objects.create(parent=cls.finished, child=cls.assembly, quantity=1)
        BomLine.objects.create(parent=cls.assembly, child=cls.com1, quantity=2)
        order = CustomerOrder.objects.create(number="21001", order_date=date(2026, 1, 5),
                                             ship_date=date(2026, 1, 20), customer="Test College")
        CustomerOrderLine.objects.create(order=order, product=cls.finished, quantity=7)
        cls.wo = WorkOrder.objects.create(number="9001", product=cls.finished, quantity=3,
                                          due_date=date(2026, 2, 1))
        Unit.objects.create(work_order=cls.wo, serial="SER-0001")
        cls.order = order

    def test_list_pages_render(self):
        for name, code in (("products", "FG1000"), ("assemblies", "SA2000"), ("components", "COM1")):
            response = self.client.get(reverse(name))
            self.assertContains(response, code)

    def test_csv_exports(self):
        response = self.client.get(reverse("products"), {"format": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv")
        text = response.content.decode()
        self.assertIn("Total cost to manufacture", text.splitlines()[0])
        self.assertIn("FG1000", text)
        self.assertIn(",7,", text)
        self.assertIn("Used in", self.client.get(reverse("assemblies"), {"format": "csv"}).content.decode())
        self.assertIn("COM1", self.client.get(reverse("components"), {"format": "csv"}).content.decode())

    def test_assembly_used_in_count(self):
        response = self.client.get(reverse("assemblies"), {"format": "csv"})
        self.assertIn("SA2000,Gantry,SA,1,", response.content.decode())

    def test_component_category_filter(self):
        response = self.client.get(reverse("components"), {"category": "FIX"})
        self.assertContains(response, "FIX1")
        self.assertNotContains(response, "COM1")
        csv_text = self.client.get(reverse("components"), {"category": "FIX", "format": "csv"}).content.decode()
        self.assertIn("FIX1", csv_text)
        self.assertNotIn("COM1", csv_text)

    def test_product_detail(self):
        response = self.client.get(reverse("product_detail", args=[self.finished.pk]))
        self.assertContains(response, "Test College")
        self.assertContains(response, reverse("customer_order", args=[self.order.pk]))
        self.assertContains(response, reverse("operator", args=[self.wo.pk]))
        self.assertContains(response, "SER-0001")
        self.assertContains(response, reverse("bom", args=[self.finished.pk]))

    def test_no_bom_button_without_bom_lines(self):
        lone = Product.objects.create(code="FG3000", name="Lone", kind=Product.FINISHED)
        response = self.client.get(reverse("product_detail", args=[lone.pk]))
        self.assertNotContains(response, "View bill of materials")

    def test_sales_csv(self):
        response = self.client.get(reverse("product_detail", args=[self.finished.pk]), {"format": "csv"})
        self.assertIn("Test College", response.content.decode())

    def test_component_redirects(self):
        response = self.client.get(reverse("product_detail", args=[self.com1.pk]))
        self.assertRedirects(response, reverse("component_detail", args=[self.com1.pk]),
                             fetch_redirect_response=False)

    def test_partials_included(self):
        from django.template.loader import get_template
        source = get_template("mes/catalogue/product_detail.html").template.source
        for partial in ("bom", "machines", "defects"):
            self.assertIn(f'{{% include "mes/{partial}/_product_panel.html" %}}', source)
        response = self.client.get(reverse("product_detail", args=[self.finished.pk]))
        self.assertEqual(response.status_code, 200)
