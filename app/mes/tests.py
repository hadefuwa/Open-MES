from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import (CustomerOrder, CustomerOrderLine, ProductionTechnician, Product, TestReport, Unit,
                     WorkOrder,
                     Workstation)


class DemoStoryTest(TestCase):
    """Walks the lifecycle: allocate, issue, start, record units, QA, complete, trace."""

    def setUp(self):
        product = Product.objects.create(code="P1", name="Widget")
        station = Workstation.objects.create(name="Assembly 1")
        self.alex = ProductionTechnician.objects.create(name="Alex")
        self.order = WorkOrder.objects.create(
            number="WO-1", product=product, quantity=2, workstation=station, due_date=date.today()
        )

    def post(self, name, *args, **data):
        return self.client.post(reverse(name, args=args), data)

    def status(self):
        self.order.refresh_from_db()
        return self.order.status

    def release(self):
        pk = self.order.pk
        self.post("allocate", pk)
        self.post("issue", pk)

    def test_full_flow(self):
        pk = self.order.pk
        self.assertEqual(self.status(), WorkOrder.ENTERED)

        # cannot start before allocate + issue
        self.post("start", pk)
        self.assertEqual(self.status(), WorkOrder.ENTERED)

        self.release()
        self.assertEqual(self.status(), WorkOrder.ISSUED)
        self.post("start", pk)
        self.assertEqual(self.status(), WorkOrder.IN_PROGRESS)

        self.post("add_unit", pk, serial="S1", result="pass")
        self.post("add_unit", pk, serial="S2", result="rework", reason="loose wire")

        # cannot go to QA while a unit is in rework
        self.post("finish", pk)
        self.assertEqual(self.status(), WorkOrder.IN_PROGRESS)

        s2 = Unit.objects.get(serial="S2")
        self.post("retest_unit", pk, s2.pk, result="pass")
        self.post("finish", pk)
        self.assertEqual(self.status(), WorkOrder.QA)

        # team leader can reject, then approve after another pass
        self.post("reject", pk)
        self.assertEqual(self.status(), WorkOrder.IN_PROGRESS)
        self.post("finish", pk)
        self.post("approve", pk)
        self.assertEqual(self.status(), WorkOrder.COMPLETE)

        s2.refresh_from_db()
        self.assertFalse(s2.first_pass)
        self.assertTrue(Unit.objects.get(serial="S1").first_pass)

        resp = self.client.get(reverse("traceability"), {"serial": "S2"})
        self.assertContains(resp, "loose wire")
        self.assertEqual(self.client.get(reverse("dashboard")).context["kpis"]["fpy"], 50.0)

    def test_rejects_duplicate_serial_and_missing_reason(self):
        pk = self.order.pk
        self.release()
        self.post("start", pk)
        self.post("add_unit", pk, serial="S1", result="pass")
        self.post("add_unit", pk, serial="S1", result="pass")
        self.post("add_unit", pk, serial="S3", result="scrap")
        self.assertEqual(Unit.objects.count(), 1)

    def test_assign_and_my_jobs(self):
        pk = self.order.pk
        self.post("assign", pk, technician=self.alex.pk)
        url = reverse("my_jobs")
        # not shown until issued
        resp = self.client.get(url, {"technician": self.alex.pk})
        self.assertEqual(len(resp.context["orders"]), 0)
        self.release()
        resp = self.client.get(url, {"technician": self.alex.pk})
        self.assertEqual(len(resp.context["orders"]), 1)

    def test_print_marks_printed(self):
        self.assertFalse(self.order.printed)
        resp = self.client.get(reverse("print_sheet", args=[self.order.pk]))
        self.assertContains(resp, "WO-1")
        self.order.refresh_from_db()
        self.assertTrue(self.order.printed)

    def test_raise_work_order_from_customer_order(self):
        co = CustomerOrder.objects.create(number="C1", order_date=date.today(), customer="Test Co")
        line = CustomerOrderLine.objects.create(order=co, product=self.order.product, quantity=4)
        url = reverse("raise_work_order", args=[co.pk, line.pk])
        self.client.post(url)
        self.client.post(url)  # raising twice must not create a second works order
        line.refresh_from_db()
        self.assertEqual(WorkOrder.objects.count(), 2)
        self.assertEqual(line.work_order.quantity, 4)
        self.assertEqual(line.work_order.status, WorkOrder.ENTERED)
        self.assertEqual(self.client.get(reverse("customer_order", args=[co.pk])).status_code, 200)

    def test_pages_render(self):
        for name, args in [("board", []), ("dashboard", []), ("traceability", []), ("my_jobs", []), ("customer_orders", []),
                           ("operator", [self.order.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)


class TestReportImportTest(TestCase):
    """Builds a tiny workbook in the expected layout and imports it."""

    def make_workbook(self, path):
        import openpyxl

        wb = openpyxl.Workbook()
        summary = wb.active
        summary.title = "Summary"
        summary.append(["Test Reports"])
        summary.append([])
        summary.append(["Report ID", "Date", "Submitted At", "Operator", "Product", "Serial Number",
                        "Build Reference", "Procedure", "Overall Result", "Total", "Passed", "Failed", "Comments"])
        summary.append(["XX-1-SN1", "2026-03-20", "2026-03-20T12:00:00.000Z", "Alex Smith", "Widget", "SN1",
                        None, "XX1", "FAIL", 3, 2, 1, "needs rework"])
        sheet = wb.create_sheet("XX-1-SN1")
        sheet.append(["Report ID", "XX-1-SN1", "Date", "2026-03-20", "Procedure", "XX1"])
        sheet.append(["Operator", "Alex Smith", "Serial Number", "SN1", "Overall Result", "FAIL"])
        sheet.append([])
        sheet.append(["Step", "Criteria", "Result", "Comments", "Sign Off"])
        sheet.append(["1. Checks", None, None, None, None])
        sheet.append(["1.1", "Look at it", "PASS", None, "MS"])
        sheet.append(["1.9", "Poke it", "PASS", None, "MS"])
        sheet.append(["1.1", "Tenth step stored as a float", "FAIL", "loose", "MS"])
        wb.save(path)

    def test_import_and_pages(self):
        import tempfile, os
        from .importers import import_test_reports

        ProductionTechnician.objects.create(name="Alex")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "reports.xlsx")
            self.make_workbook(path)
            self.assertEqual(import_test_reports(path), 1)
            self.assertEqual(import_test_reports(path), 0)  # importing twice must not duplicate

        report = TestReport.objects.get(report_id="XX-1-SN1")
        self.assertEqual(report.steps.count(), 3)
        self.assertEqual([s.number for s in report.steps.all()], ["1.1", "1.9", "1.10"])
        self.assertEqual(report.tester, "Alex")
        self.assertFalse(report.passed)
        unit = report.unit
        self.assertEqual((unit.serial, unit.result, unit.first_pass), ("SN1", Unit.REWORK, False))
        self.assertEqual(unit.work_order.status, WorkOrder.COMPLETE)

        self.assertContains(self.client.get(reverse("test_reports")), "XX-1-SN1")
        self.assertContains(self.client.get(reverse("test_report", args=[report.pk])), "Tenth step")
        self.assertContains(self.client.get(reverse("traceability"), {"serial": "SN1"}), "View test report")
