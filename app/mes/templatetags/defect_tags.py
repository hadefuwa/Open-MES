from decimal import Decimal

from django import template

from .. import views_defects
from ..models import Defect, Unit

register = template.Library()


@register.simple_tag
def defect_part_choices(order):
    return views_defects.component_choices(order)


@register.simple_tag
def defect_order_units(order):
    return Unit.objects.filter(work_order=order).order_by("serial")


@register.simple_tag
def defect_summary(product):
    """Defects while building `product` plus defects where it was the faulty part."""
    built = list(product.defects.select_related("component", "work_order", "unit"))
    faulty = list(product.defects_as_component.select_related("product", "work_order", "unit"))
    rows = sorted(built + [d for d in faulty if d not in built],
                  key=lambda d: (d.occurred_at, d.pk), reverse=True)
    return {
        "rows": rows[:5],
        "count": len(rows),
        "quantity": sum(d.quantity for d in rows),
        "cost": sum((d.cost for d in rows), Decimal("0")),
        "built": len(built),
        "faulty": len(faulty),
    }
