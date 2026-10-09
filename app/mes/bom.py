"""BOM helpers: indented explosion, where-used and flattened component totals. All cycle-safe."""
from dataclasses import dataclass, field
from decimal import Decimal

from . import costing
from .models import BomLine, Product

ZERO = Decimal("0")


@dataclass
class ExplodedRow:
    level: int
    line: BomLine
    child: Product
    quantity: Decimal          # per immediate parent
    ext_quantity: Decimal      # cumulative multiplier from the root product
    unit_cost: Decimal         # rolled-up for assemblies, purchase cost for components
    is_assembly: bool
    minutes: Decimal           # own routing minutes of the child (per unit)
    ext_cost: Decimal = ZERO

    @property
    def line_cost(self):
        return self.quantity * self.unit_cost

    @property
    def indent(self):
        return self.level * 22


def explode(product):
    """Depth-first indented explosion of `product` as a list of ExplodedRow."""
    rows, costs = [], {}

    def unit_cost(p):
        if p.pk not in costs:
            costs[p.pk] = costing.bom_cost(p)
        return costs[p.pk]

    def walk(parent, level, multiplier, stack):
        for line in parent.bom_lines.select_related("child").order_by("sequence", "child__code"):
            child = line.child
            if child.pk in stack:
                continue
            ext_qty = multiplier * line.quantity
            has_lines = child.bom_lines.exists()
            cost = unit_cost(child)
            rows.append(ExplodedRow(
                level=level, line=line, child=child, quantity=line.quantity, ext_quantity=ext_qty,
                unit_cost=cost, is_assembly=has_lines, minutes=costing.own_build_minutes(child),
                ext_cost=ext_qty * cost))
            if has_lines:
                walk(child, level + 1, ext_qty, stack + (child.pk,))

    walk(product, 0, Decimal(1), (product.pk,))
    return rows


def where_used_direct(product):
    """BomLine rows in which `product` is the child."""
    return list(product.used_in.select_related("parent").order_by("parent__code"))


@dataclass
class WhereUsed:
    product: Product
    paths: list = field(default_factory=list)   # each path runs from `product` down to the searched item
    quantity: Decimal = ZERO                    # effective quantity per unit of `product`

    @property
    def is_finished(self):
        return self.product.kind == Product.FINISHED

    @property
    def direct(self):
        return any(len(p) == 2 for p in self.paths)


def where_used_all(product):
    """Every ancestor of `product` with each path to it and the effective quantity per ancestor."""
    found = {}

    def climb(node, path, qty, stack):
        for line in node.used_in.select_related("parent"):
            parent = line.parent
            if parent.pk in stack:
                continue
            new_path = [parent] + path
            new_qty = qty * line.quantity
            entry = found.setdefault(parent.pk, WhereUsed(product=parent))
            entry.paths.append(new_path)
            entry.quantity += new_qty
            climb(parent, new_path, new_qty, stack + (parent.pk,))

    climb(product, [product], Decimal(1), (product.pk,))
    result = list(found.values())
    result.sort(key=lambda w: (not w.is_finished, w.product.code))
    return result


@dataclass
class FlatComponent:
    product: Product
    quantity: Decimal
    unit_cost: Decimal
    cost: Decimal
    used_in: int = 0


def flat_components(product):
    """Total quantity and cost of every leaf component across the whole tree."""
    totals = {}
    for row in explode(product):
        if row.is_assembly:
            continue
        entry = totals.setdefault(row.child.pk, FlatComponent(row.child, ZERO, row.unit_cost, ZERO))
        entry.quantity += row.ext_quantity
        entry.cost += row.ext_cost
        entry.used_in += 1
    return sorted(totals.values(), key=lambda f: f.product.code)
