"""Planning demo data: open work orders spread over the next weeks, fictional customer orders with ship
dates, and the links between them, so the timeline looks full. Everything here is invented."""
from datetime import datetime, time, timedelta

from django.db.models import IntegerField, Max
from django.db.models.functions import Cast
from django.utils import timezone

from mes.models import CustomerOrder, CustomerOrderLine, Unit, WorkOrder

E, A, I, P = WorkOrder.ENTERED, WorkOrder.ALLOCATED, WorkOrder.ISSUED, WorkOrder.IN_PROGRESS


def seed(ctx):
    """Open work orders and customer orders spread over the next weeks, from the pack's PLANNING_ORDERS and
    STOCK_BUILDS, plus links between them so the timeline looks full."""
    rng, today = ctx.rng, ctx.today
    stations = list(ctx.stations.values())
    top = WorkOrder.objects.filter(number__regex=r"^\d+$").annotate(
        n=Cast("number", IntegerField())).aggregate(m=Max("n"))["m"] or 3400
    counter = [top]

    def make_wo(code, qty, status, due_in, tech, created):
        counter[0] += 1
        product = ctx.products[code]
        due = today + timedelta(days=due_in)
        start = due - timedelta(days=2 + qty // 3)
        minutes = product.build_minutes
        wo = WorkOrder.objects.create(
            number=str(counter[0]), product=product, quantity=qty, workstation=rng.choice(stations),
            technician=ctx.technicians.get(tech), start_date=start, due_date=due, status=status,
            printed=status in (I, P, WorkOrder.COMPLETE), est_minutes=int(minutes * qty) if minutes else None)
        if status == P:
            for n in range(max(1, int(qty * rng.uniform(0.3, 0.7)))):
                Unit.objects.create(work_order=wo, serial=f"{code}-{wo.number}-{n + 1:02d}", result=Unit.PASS)
        WorkOrder.objects.filter(pk=wo.pk).update(created_at=created, updated_at=created + timedelta(hours=rng.randint(2, 40)))
        return wo

    for number, ago, customer, ship_in, lines in ctx.pack.PLANNING_ORDERS:
        ordered = today - timedelta(days=ago)
        stamp = _stamp(ordered)
        order = CustomerOrder.objects.create(
            number=number, order_date=ordered, ship_date=today + timedelta(days=ship_in), customer=customer,
            customer_ref=f"PO-{rng.randint(10000, 99999)}", created_at=stamp)
        for spec in lines:
            code, qty = spec[:2]
            wo = make_wo(*spec, stamp + timedelta(hours=1)) if len(spec) > 2 else None
            CustomerOrderLine.objects.create(order=order, product=ctx.products[code], quantity=qty,
                                             work_order=wo, created_at=stamp)
        CustomerOrder.objects.filter(pk=order.pk).update(updated_at=stamp + timedelta(hours=rng.randint(1, 60)))

    for code, qty, status, due_in, tech in ctx.pack.STOCK_BUILDS:
        make_wo(code, qty, status, due_in, tech, _stamp(today - timedelta(days=rng.randint(2, 9))))

    # Tie the base seed's customer orders to the open work orders for the same product where one exists.
    base_numbers = {o[0] for o in getattr(ctx.pack, "CUSTOMER_ORDERS", [])}
    own_numbers = {o[0] for o in ctx.pack.PLANNING_ORDERS}
    for line in CustomerOrderLine.objects.filter(order__number__in=base_numbers, work_order__isnull=True):
        match = WorkOrder.objects.filter(product=line.product).exclude(status=WorkOrder.COMPLETE).first()
        if match:
            line.work_order = match
            line.save(update_fields=["work_order"])

    # Recent history from the sales-history area: treat its orders as built and shipped, so only the
    # deliberate late order above shows as late.
    recent = CustomerOrder.objects.filter(
        ship_date__lt=today, ship_date__gte=today - timedelta(days=21)).exclude(number__in=own_numbers)
    for order in recent.prefetch_related("lines"):
        for line in order.lines.filter(work_order__isnull=True):
            wo = make_wo(line.product.code, line.quantity, WorkOrder.COMPLETE,
                         (order.ship_date - today).days - 2, rng.choice(list(ctx.technicians)),
                         _stamp(order.order_date))
            line.work_order = wo
            line.save(update_fields=["work_order"])


def _stamp(day):
    return timezone.make_aware(datetime.combine(day, time(9, 0)))
