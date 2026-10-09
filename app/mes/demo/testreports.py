"""Generic test reports for the demo: a standard procedure run against a few completed units, with one failure,
so the Test reports page has something to show without importing any workbook."""
from datetime import datetime, time, timedelta

from django.utils import timezone

from mes.models import TestReport, TestStep, Unit, WorkOrder

PROCEDURE = "TP-100"
SECTIONS = [
    ("1. Documentation", ["Latest drawings and test sheet to hand", "Test equipment in calibration"]),
    ("2. Visual inspection", ["No physical damage; labels legible", "All fixings tight and wires labelled"]),
    ("3. Dead testing", ["Supply disconnected; no indicators lit", "Continuity of all wiring confirmed",
                         "Insulation resistance within limits"]),
    ("4. Power-up", ["Supply on; status indicators correct", "Controller boots without faults"]),
    ("5. Functional test", ["All inputs respond as drawn", "All outputs operate correctly", "Emergency stop and reset work"]),
    ("6. Sign-off", ["Comments recorded", "Test sheet signed"]),
]
COMMENTS = ["", "", "Back plate to be fitted before dispatch", "", "Re-tested after loose terminal tightened", ""]


def seed(ctx):
    rng = ctx.rng
    units = list(Unit.objects.filter(work_order__status=WorkOrder.COMPLETE, result=Unit.PASS)
                 .select_related("work_order__product").order_by("created_at"))
    if not units:
        return
    technicians = list(ctx.technicians.values())
    for number, unit in enumerate(units[-6:], start=1):
        tech = rng.choice(technicians)
        when = unit.created_at + timedelta(hours=1)
        failed = number == 4
        report = TestReport.objects.create(
            report_id=f"{PROCEDURE}-{unit.serial}", procedure=PROCEDURE, product=unit.work_order.product,
            unit=unit, serial=unit.serial, operator_name=tech.name, technician=tech,
            test_date=when.date(), submitted_at=when, overall_result="FAIL" if failed else "PASS",
            comments=COMMENTS[number - 1])
        if failed:  # the first test failed, the fault was fixed and the unit passed on re-test
            Unit.objects.filter(pk=unit.pk).update(first_pass=False, reason="Loose terminal on X2")
        order, steps = 0, []
        for section, items in SECTIONS:
            for n, text in enumerate(items, start=1):
                order += 1
                result = "FAIL" if failed and order == 8 else "PASS"
                steps.append(TestStep(report=report, order=order, section=section,
                                      number=f"{section.split('.')[0]}.{n}", criteria=text, result=result,
                                      comments="Loose terminal on X2" if result == "FAIL" else "",
                                      sign_off=tech.name[:2].upper()))
        TestStep.objects.bulk_create(steps)
        TestReport.objects.filter(pk=report.pk).update(created_at=when, updated_at=when)
