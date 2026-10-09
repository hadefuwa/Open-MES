"""Derived manufacturing figures: build time, BOM cost and total cost to manufacture.

Everything is calculated from BomLine, RoutingStep and Product.unit_cost; nothing is
stored by hand. All functions are cycle-safe.
"""
from decimal import Decimal

from django.conf import settings

ZERO = Decimal("0")


def labour_rate():
    """Labour cost per hour."""
    return Decimal(str(getattr(settings, "MES_LABOUR_RATE_PER_HOUR", 28)))


def _children(product):
    return list(product.bom_lines.select_related("child"))


def own_build_minutes(product):
    """Minutes in this product's own routing (not including sub-assemblies)."""
    return sum((s.minutes for s in product.routing_steps.all()), ZERO)


def total_build_minutes(product, _stack=()):
    """Own routing plus the build time of every sub-assembly, scaled by BOM quantity."""
    if product.pk in _stack:
        return ZERO
    stack = _stack + (product.pk,)
    total = own_build_minutes(product)
    for line in _children(product):
        total += line.quantity * total_build_minutes(line.child, stack)
    return total


def bom_cost(product, _stack=()):
    """Material cost: purchase cost for a leaf, otherwise the quantity-weighted sum of children."""
    if product.pk in _stack:
        return ZERO
    lines = _children(product)
    if not lines:
        return product.unit_cost or ZERO
    stack = _stack + (product.pk,)
    return sum((line.quantity * bom_cost(line.child, stack) for line in lines), ZERO)


def labour_cost(product):
    return total_build_minutes(product) / Decimal(60) * labour_rate()


def total_cost(product):
    """Total cost to manufacture: BOM cost + build time x labour rate."""
    return bom_cost(product) + labour_cost(product)


def would_create_cycle(parent, child):
    """True if adding parent -> child would make `parent` a descendant of itself."""
    seen, todo = set(), [child]
    while todo:
        node = todo.pop()
        if node.pk == parent.pk:
            return True
        if node.pk in seen:
            continue
        seen.add(node.pk)
        todo.extend(line.child for line in node.bom_lines.select_related("child"))
    return False
