import os
import tempfile
from decimal import Decimal

from django.test import TestCase

from . import bom_import, classify
from .models import BomLine, CustomerOrder, CustomerOrderLine, Product, RoutingStep


def make_workbook(path):
    import openpyxl

    wb = openpyxl.Workbook()
    ex = wb.active
    ex.title = "Explosion"
    ex.append(["Bom Level", "Parent", "Bom Structure", "Description", "Seq.", "Quantity", "Unit"])
    ex.append([0, None, "TOP1", "Top product"])
    ex.append([1, "TOP1", "SUB1", "Sub assembly", 5, 2, None])
    ex.append([2, "SUB1", "COM1", "Motor", 10, 1, "Each"])
    ex.append([2, "SUB1", "FIX1", "Screw", 20, 8, None])
    ex.append([1, "TOP1", "FIX1", "Screw", 30, 4, None])
    stock = wb.create_sheet("Sheet1")
    stock.append(["Product Code", "Description", "Supplier A/C", "Part No.", "Quantity Allocated", "Quantity On Order",
                  "Re-Order Level", "Re-Order Quantity", "Last Cost Price (Std)", "Last Order Quantity",
                  "Last Order Date", "Free Stock"])
    stock.append(["COM1", "Motor, stepper", "M3000", "NEMA17", 0, 0, 5, 10, 9.5, 0, None, 3])
    stock.append(["FIX1", "Screw M3", "M3000", "", 0, 0, 100, 500, 0.0123, 0, None, 800])
    stock.append(["NEW1", "Stocked but unused part", "S1", "", 0, 0, 0, 0, 1.25, 0, None, 7])
    accounts = wb.create_sheet("Accounts")  # customer accounts must be ignored entirely
    accounts.append(["A/C", "Name", "Payment Due"])
    accounts.append(["85562", "Some Customer Ltd", 0])
    wb.save(path)


class BomImportTest(TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bom.xlsx")
            make_workbook(path)
            self.summary = bom_import.import_workbook(path)

    def test_explosion_builds_relational_bom(self):
        self.assertEqual(self.summary["bom_lines"], 4)
        top, sub = Product.objects.get(code="TOP1"), Product.objects.get(code="SUB1")
        self.assertEqual(BomLine.objects.get(parent=top, child=sub).quantity, Decimal("2.00"))
        self.assertEqual(BomLine.objects.get(parent=sub, child__code="FIX1").quantity, Decimal("8.00"))
        self.assertEqual(Product.objects.get(code="COM1").name, "Motor")

    def test_stock_master_sets_cost_stock_and_supplier_and_skips_other_sheets(self):
        com = Product.objects.get(code="COM1")
        self.assertEqual((com.unit_cost, com.free_stock, com.reorder_level, com.supplier_code, com.supplier_part_no),
                         (Decimal("9.5000"), 3, 5, "M3000", "NEMA17"))
        self.assertTrue(com.low_stock)
        self.assertEqual(Product.objects.get(code="FIX1").unit_cost, Decimal("0.0123"))  # fractions of a penny kept
        self.assertEqual(Product.objects.get(code="NEW1").kind, Product.COMPONENT)
        self.assertFalse(Product.objects.filter(code="85562").exists())  # accounts sheet ignored

    def test_reimport_replaces_instead_of_stacking(self):
        before = BomLine.objects.count()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bom.xlsx")
            make_workbook(path)
            bom_import.import_workbook(path)
        self.assertEqual(BomLine.objects.count(), before)

    def test_kinds_come_from_bom_structure(self):
        kinds = classify.classify_kinds()
        self.assertEqual(Product.objects.get(code="TOP1").kind, Product.FINISHED)
        self.assertEqual(Product.objects.get(code="SUB1").kind, Product.ASSEMBLY)
        self.assertEqual(Product.objects.get(code="COM1").kind, Product.COMPONENT)
        self.assertEqual(kinds[Product.FINISHED], 1)

    def test_spares_versus_systems_by_description_and_price(self):
        mk = lambda code, name, rrp: Product.objects.create(code=code, name=name, rrp=Decimal(rrp), kind=Product.FINISHED)
        mk("T1", "Tubing, 4mm, red, 30 m length", "18")
        mk("T2", "Cylinder, double acting, 10 * 80 mm", "81")
        mk("T3", "Ammeter 0A to 1A", "26")
        mk("T4", "Electrical machines 2.0 training system", "11450")
        mk("T5", "Smart Sensors IO Link", "2500")
        mk("T6", "Logic trainer add on (DIN)", "248")
        sold = mk("T7", "Power supply", "12.55")
        co = CustomerOrder.objects.create(number="C1", order_date="2026-01-01", customer="X")
        CustomerOrderLine.objects.create(order=co, product=sold, quantity=1)
        classify.classify_kinds()
        kind = lambda code: Product.objects.get(code=code).kind
        self.assertEqual([kind(c) for c in ("T1", "T2", "T3")], [Product.COMPONENT] * 3)
        self.assertEqual([kind(c) for c in ("T4", "T5", "T6", "T7")], [Product.FINISHED] * 4)

    def test_missing_costs_are_filled_deterministically_and_routings_added(self):
        Product.objects.create(code="COM9", name="No cost", kind=Product.COMPONENT, category="COM")
        classify.classify_kinds()  # TOP1 and SUB1 are not components, so only COM9 needs a cost
        self.assertEqual(bom_import.fill_missing_costs(), 1)
        cost = Product.objects.get(code="COM9").unit_cost
        self.assertTrue(Decimal("0.4") <= cost <= Decimal("18"))
        self.assertEqual(bom_import.estimated_cost("COM9", "COM"), cost)
        classify.classify_kinds()
        self.assertGreaterEqual(bom_import.ensure_routings(), 2)  # TOP1 and SUB1 had no routing
        self.assertTrue(RoutingStep.objects.filter(product__code="TOP1").exists())


def make_design_workbook(path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "XY0123 BOM"
    ws.append(["TYPE", "ITEM NO.", "DESCRIPTION", "New Part?", "Own Part Name", "Location", "Cost", "Pack size",
               "Supplier", "Order Product Code", "URL", "Secondary Supplier", "Existing Billet", "Material",
               "Thickness", "Metal/Plastic Laser", "Mass", "Time to print (per 1)", "Finish", "Sheet", "Yield",
               "Number of Bends", "QTY."])

    def row(kind, item, desc, code, cost, pack, supplier, order, qty, print_time=None):
        values = [None] * 23
        values[0], values[1], values[2], values[4] = kind, item, desc, code
        values[6], values[7], values[8], values[9], values[22], values[17] = cost, pack, supplier, order, qty, print_time
        ws.append(values)

    row("Fixtures", 1, "M3 washer", "FIX1", 1.14, 100, "RS", "RS-123", 4)
    row(None, 2, "M3 washer again", "FIX1", 1.14, 100, "RS", "RS-123", 6)  # same part on a second line
    row("3DPrints", 3, "Printed spacer", "3DP1", None, 1, "In-house", None, 2, "10m30s")
    row("CNC parts", 4, "Port adapter", "CNC1", 25, 1, "In-house", None, 1)
    row("Components", 5, "Engine", "COM1", 105, 1, "Kontax", None, 1)
    ws.append([None] * 22 + [43])  # trailing total row without a code is ignored
    wb.save(path)


class DesignBomImportTest(TestCase):
    def setUp(self):
        from . import bom_import as bi
        from .models import Machine
        Machine.objects.create(name="3D printer farm")
        Machine.objects.create(name="CNC Mill")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "XY0123 BOM.xlsx")  # the product code comes from the file name
            make_design_workbook(path)
            self.summary = bi.import_workbook(path, names={"XY0123": "Test Engine"})

    def test_builds_bom_for_the_product_named_in_the_file(self):
        top = Product.objects.get(code="XY0123")
        self.assertEqual(top.name, "Test Engine")
        self.assertEqual(top.bom_lines.count(), 4)
        self.assertEqual(self.summary["bom_lines"], 4)

    def test_duplicate_lines_are_summed_and_cost_is_per_pack(self):
        top = Product.objects.get(code="XY0123")
        washer = BomLine.objects.get(parent=top, child__code="FIX1")
        self.assertEqual(washer.quantity, Decimal("10.00"))
        self.assertEqual(washer.child.unit_cost, Decimal("0.0114"))  # 1.14 per pack of 100
        self.assertEqual(washer.child.supplier_part_no, "RS-123")
        self.assertEqual(Product.objects.get(code="COM1").unit_cost, Decimal("105.0000"))

    def test_in_house_parts_get_routing_on_the_right_machine(self):
        printed = RoutingStep.objects.get(product__code="3DP1")
        self.assertEqual((printed.machine.name, printed.minutes), ("3D printer farm", Decimal("10.5")))
        cnc = RoutingStep.objects.get(product__code="CNC1")
        self.assertEqual(cnc.machine.name, "CNC Mill")
        self.assertFalse(RoutingStep.objects.filter(product__code="FIX1").exists())  # bought in
        # build time on the parent includes the in-house parts (2 prints x 10.5 + 10 for the CNC part)
        self.assertEqual(Product.objects.get(code="XY0123").build_minutes, Decimal("31.0"))

    def test_reimport_does_not_stack(self):
        from . import bom_import as bi
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "XY0123 BOM.xlsx")
            make_design_workbook(path)
            bi.import_workbook(path)
        self.assertEqual(BomLine.objects.filter(parent__code="XY0123").count(), 4)
        self.assertEqual(RoutingStep.objects.filter(product__code="3DP1").count(), 1)
