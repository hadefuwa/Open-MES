from django import template

from .. import costing

register = template.Library()

STATUS_PILL = {"available": "ok", "in_use": "info", "maintenance": "warn", "down": "bad"}


@register.simple_tag
def routing_panel(product):
    steps = list(product.routing_steps.select_related("machine"))
    return {
        "steps": [{"step": s, "pill": STATUS_PILL.get(s.machine.status, "") if s.machine else ""} for s in steps],
        "minutes": costing.own_build_minutes(product),
        "blocked": sorted({s.machine for s in steps if s.machine and not s.machine.is_available},
                          key=lambda m: m.name),
    }
