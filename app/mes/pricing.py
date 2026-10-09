"""Import a price list and tie manufacturing cost to RRP.

The workbook needs a "Prices" sheet with columns Code | Description | RRP. Rows with a code and no
description or price are section headings (the product range, e.g. "Renewables").

Cost rule used by the demo: the bill-of-materials cost of a product is about a third of its RRP.
  * products with no BOM: unit_cost = RRP / 3
  * products with a modelled BOM: a line of "other materials" tops the BOM up to exactly RRP / 3,
    standing in for parts that are not itemised in the demo data
  * modelled products missing from the price list get an estimated RRP (3x materials, at least
    2.5x the full cost) and are flagged rrp_estimated
"""
from decimal import ROUND_HALF_UP, Decimal

from .models import BomLine, Product
from . import costing

COST_RATIO = Decimal(3)
OTHER_MATERIALS_CODE = "OTH0001"
CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def read_price_list(path, skip_sections=()):
    """Returns [(range name, code, description, price)] for every priced row (first occurrence of a code).

    `skip_sections` lists prefixes (lower case) of title or note rows that look like section headings but
    are not product ranges."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        rows = list(workbook["Prices"].iter_rows(values_only=True))
    finally:
        workbook.close()  # read-only workbooks keep the file locked on Windows until closed
    section, seen, items = "", set(), []
    for row in rows:
        code, desc, price = (list(row) + [None] * 3)[:3]
        if code and desc is None and price is None:
            text = str(code).replace("\n", " ").strip()
            if not text.lower().startswith(tuple(skip_sections)):
                section = text
        elif code and isinstance(price, (int, float)) and price > 0:
            code = str(code).strip()
            if code not in seen:
                seen.add(code)
                items.append((section, code, str(desc or "").strip(), _money(price)))
    return items


def import_price_list(path, skip_sections=(), estimate_cost=True):
    """Create or update products from the price list. Returns (created, updated).

    With `estimate_cost`, newly created products get a unit cost of RRP / 3 (a demo convenience). Turn it
    off to leave the cost blank until real costs are imported."""
    created = updated = 0
    for section, code, desc, price in read_price_list(path, skip_sections):
        product = Product.objects.filter(code=code).first()
        if product is None:
            Product.objects.create(code=code, name=desc or code, kind=Product.FINISHED, rrp=price,
                                   range_name=section,
                                   unit_cost=_money(price / COST_RATIO) if estimate_cost else None)
            created += 1
        else:
            product.rrp, product.rrp_estimated = price, False
            product.range_name = product.range_name or section
            if desc and product.kind != Product.COMPONENT:
                product.name = desc
            product.save()
            updated += 1
    return created, updated


def calibrate_costs():
    """Apply the cost rule (see module docstring). Returns a dict of counts."""
    other, _ = Product.objects.get_or_create(
        code=OTHER_MATERIALS_CODE,
        defaults={"name": "Other materials (not itemised in this demo BOM)", "kind": Product.COMPONENT,
                  "category": "OTH", "unit_cost": Decimal("1.00")})
    stats = {"topped_up": 0, "made_leaf": 0, "estimated_rrp": 0}

    modelled = Product.objects.filter(kind=Product.FINISHED, bom_lines__isnull=False).distinct()
    for product in modelled:
        BomLine.objects.filter(parent=product, child=other).delete()
        current = costing.bom_cost(product)
        if product.rrp is None:
            # 3x materials, but never less than 2.5x the full cost (labour dominates cheap items)
            estimate = max(current * COST_RATIO, (current + costing.labour_cost(product)) * Decimal("2.5"))
            product.rrp = (estimate / 5).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 5
            product.rrp_estimated = True
            product.save()
            stats["estimated_rrp"] += 1
            continue
        shortfall = product.rrp / COST_RATIO - current
        if shortfall >= CENT:
            BomLine.objects.create(parent=product, child=other, quantity=_money(shortfall), sequence=9999)
            stats["topped_up"] += 1
        elif shortfall < 0 and product.bom_lines.count() <= 3:
            # A tiny BOM that already costs more than a third of RRP (e.g. a resold power supply):
            # treat the product as a bought-in item instead of a build. Real, long BOMs are kept.
            product.bom_lines.all().delete()
            product.unit_cost = _money(product.rrp / COST_RATIO)
            product.save()
            stats["made_leaf"] += 1

    # Finished products with no BOM are priced from RRP; spare parts keep their real stock cost.
    for product in Product.objects.filter(kind=Product.FINISHED, bom_lines__isnull=True, rrp__isnull=False):
        product.unit_cost = _money(product.rrp / COST_RATIO)
        product.save(update_fields=["unit_cost"])
    return stats
