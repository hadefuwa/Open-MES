from django import template

from .. import bom, costing

register = template.Library()


@register.simple_tag
def first_level_bom(product):
    out = []
    for line in product.bom_lines.select_related("child"):
        cost = costing.bom_cost(line.child)
        out.append((line, cost, cost * line.quantity))
    return out


@register.simple_tag
def direct_where_used(product):
    return bom.where_used_direct(product)


@register.simple_tag
def finished_where_used(product):
    return [w for w in bom.where_used_all(product) if w.is_finished]


@register.filter
def money(value):
    """£ with 2 decimals, or 4 for amounts under 10p so tiny parts (screws, washers) are not shown as £0.00."""
    from decimal import Decimal
    if value in (None, ""):
        return "-"
    amount = Decimal(str(value))
    return f"£{amount:.4f}" if amount and abs(amount) < Decimal("0.1") else f"£{amount:,.2f}"
