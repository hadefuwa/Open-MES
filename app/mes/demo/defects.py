from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from mes import bom, costing
from mes.models import Defect, Unit, WorkOrder

COMPONENT_ISSUES = [
    "Solder bridge on pads", "Cracked acrylic on fitting", "Wrong screw fitted", "PCB mis-fit in housing",
    "Laser cut out of tolerance", "Damaged cable on crimp", "Bent pin on connector", "Thread stripped on assembly",
    "Cosmetic scratch on panel", "Failed continuity check", "Dry joint found at test", "Dropped during handling",
]
UNIT_ISSUES = [
    "Failed pressure test, unit scrapped", "Failed final test, unrecoverable", "Water damage in storage",
    "Housing cracked during assembly", "Wrong firmware, board damaged on reflash",
]


def seed(ctx):
    """About 45 defects over the last 45 days, skewed so a few parts and products dominate."""
    rng = ctx.rng
    orders = list(WorkOrder.objects.select_related("product", "technician")
                  .exclude(status=WorkOrder.ENTERED))
    candidates = []
    for order in orders:
        parts = [f.product for f in bom.flat_components(order.product)]
        if parts:
            candidates.append((order, parts))
    if not candidates:
        return
    technicians = list(ctx.technicians.values())
    hot_orders = candidates[:3]
    cost_cache = {}
    now = timezone.now()

    for _ in range(45):
        order, parts = rng.choice(hot_orders) if rng.random() < 0.45 else rng.choice(candidates)
        days_ago = int(rng.triangular(0, 45, 8))
        when = timezone.make_aware(datetime.combine(
            ctx.today - timedelta(days=days_ago), time(rng.randint(8, 16), rng.randint(0, 59))))
        if when > now:
            when = now - timedelta(minutes=rng.randint(5, 240))
        units = list(Unit.objects.filter(work_order=order))
        unit = rng.choice(units) if units and rng.random() < 0.6 else None

        if rng.random() < 0.22:
            component, quantity = None, 1
            if order.product.pk not in cost_cache:
                cost_cache[order.product.pk] = costing.total_cost(order.product)
            unit_cost = cost_cache[order.product.pk]
            description = rng.choice(UNIT_ISSUES)
        else:
            weights = [4 if i < 2 else 1 for i in range(len(parts))]
            component = rng.choices(parts, weights)[0]
            quantity = rng.choice([1, 1, 2, 3, 4, 6, 8, 12]) if component.unit_cost < 5 else rng.choice([1, 1, 2])
            unit_cost = component.unit_cost
            description = rng.choice(COMPONENT_ISSUES[:5] if rng.random() < 0.5 else COMPONENT_ISSUES)

        defect = Defect.objects.create(
            occurred_at=when, product=order.product, component=component, work_order=order, unit=unit,
            quantity=quantity, unit_cost=Decimal(unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            description=description, reported_by=order.technician or rng.choice(technicians))
        Defect.objects.filter(pk=defect.pk).update(created_at=when, updated_at=when)
