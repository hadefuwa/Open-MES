"""Planning calendar: what has to be built when, and shipped when.

The chart is plain server-rendered HTML/CSS. Every day is a fixed-width column (DAY_PX) so a bar's
position and width are simple multiples of one CSS variable.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlencode

from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse

from .models import CustomerOrder, Product, ProductionTechnician, WorkOrder
from .tables import Column, build_table

DAY_PX = 26
LABEL_PX = 230
WEEK_CHOICES = [4, 8, 12, 16]
DEFAULT_WEEKS = 8
WEEKS_BACK = 2
LATE_LOOKBACK_DAYS = 21  # older past ship dates are assumed shipped: there is no shipped flag
INSIDE_LABEL_PX = 170

STATUS_FILTERS = [("open", "Open only"), ("all", "All statuses")] + [
    (key, label) for key, label in WorkOrder.STATUS_CHOICES]


@dataclass
class Item:
    """One row of the table under the chart (and the data behind each bar or marker)."""
    kind: str
    number: str
    url: str
    product: str
    customer: str
    start: date | None
    end: date | None
    status: str
    tone: str
    technician: str
    updated: object


@dataclass
class Params:
    product: str = ""
    tech: str = ""
    status: str = "open"
    weeks: int = DEFAULT_WEEKS
    shift: int = 0

    @classmethod
    def from_request(cls, get):
        def number(key, default, allowed=None):
            try:
                value = int(get.get(key, default))
            except (TypeError, ValueError):
                return default
            return value if allowed is None or value in allowed else default

        status = get.get("status", "open")
        if status not in dict(STATUS_FILTERS):
            status = "open"
        return cls(product=get.get("product", "") if get.get("product", "").isdigit() else "",
                   tech=get.get("tech", "") if get.get("tech", "").isdigit() else "",
                   status=status, weeks=number("weeks", DEFAULT_WEEKS, WEEK_CHOICES),
                   shift=max(-52, min(52, number("shift", 0))))

    def query(self, **over):
        values = {**self.__dict__, **over}
        defaults = Params().__dict__
        return "?" + urlencode({k: v for k, v in values.items() if v not in ("", None) and v != defaults[k]})


def _monday(day):
    return day - timedelta(days=day.weekday())


def order_state(order, today):
    """(label, tone, late) for a customer order, from its linked work orders."""
    lines = list(order.lines.all())
    orders = [line.work_order for line in lines if line.work_order_id]
    unlinked = any(not line.work_order_id for line in lines) or not lines
    done = bool(lines) and not unlinked and all(wo.status == WorkOrder.COMPLETE for wo in orders)
    ship = order.ship_date
    if ship and ship < today:
        if done or ship < today - timedelta(days=LATE_LOOKBACK_DAYS):
            return "Shipped" if done else "Assumed shipped", "ok", False
        return "Late", "bad", True
    if unlinked:
        return "No works order", "warn", False
    if done:
        return "Built", "ok", False
    if ship and any(wo.due_date and wo.due_date > ship and wo.status != WorkOrder.COMPLETE for wo in orders):
        return "At risk", "bad", False
    return "In build", "info", False


def _order_matches(order, p, today):
    lines = list(order.lines.all())
    if p.product and not any(str(line.product_id) == p.product for line in lines):
        return False
    if p.tech and not any(line.work_order and str(line.work_order.technician_id) == p.tech for line in lines):
        return False
    if p.status == "all":
        return True
    state, _, _ = order_state(order, today)
    if p.status == "open":
        return state not in ("Shipped", "Assumed shipped")
    return any(line.work_order and line.work_order.status == p.status for line in lines)


def _tip(lines):
    return "\n".join(line for line in lines if line)


def _wo_tip(wo, customers):
    units = f"{wo.units_recorded} of {wo.quantity} units recorded"
    return _tip([
        f"Works order {wo.number}" + ("  (OVERDUE)" if wo.is_overdue else ""),
        f"{wo.product.code} {wo.product.name}",
        f"Quantity {wo.quantity}  |  {wo.get_status_display()}  |  {units}",
        f"Start {wo.start_date:%a %d %b %Y}" if wo.start_date else "No start date",
        f"Due {wo.due_date:%a %d %b %Y}" if wo.due_date else "No due date",
        f"Technician: {wo.technician.name}" if wo.technician else "Technician: unassigned",
        f"Workstation: {wo.workstation.name}" if wo.workstation else "",
        f"For: {', '.join(customers)}" if customers else "",
    ])


def _customers(wo):
    return sorted({line.order.customer for line in wo.order_lines.all()})


def _wo_item(wo):
    tone = "ok" if wo.status == WorkOrder.COMPLETE else "bad" if wo.is_overdue else \
        "info" if wo.status == WorkOrder.IN_PROGRESS else "warn" if wo.due_soon else ""
    label = wo.get_status_display() + (" (overdue)" if wo.is_overdue else "")
    return Item("Build", wo.number, reverse("operator", args=[wo.pk]), wo.product.code,
                ", ".join(_customers(wo)), wo.start_date, wo.due_date, label, tone,
                wo.technician.name if wo.technician else "", wo.updated_at)


def _order_item(order, state, tone):
    lines = list(order.lines.all())
    products = ", ".join(f"{line.product.code} x{line.quantity}" for line in lines)
    techs = sorted({line.work_order.technician.name for line in lines
                    if line.work_order and line.work_order.technician})
    return Item("Ship", order.number, reverse("customer_order", args=[order.pk]), products, order.customer,
                order.order_date, order.ship_date, state, tone, ", ".join(techs), order.updated_at)


def _kpis(today):
    week_end = today + timedelta(days=6 - today.weekday())
    open_orders = WorkOrder.objects.exclude(status=WorkOrder.COMPLETE)
    recent = CustomerOrder.objects.filter(
        ship_date__lt=today, ship_date__gte=today - timedelta(days=LATE_LOOKBACK_DAYS)
    ).prefetch_related("lines__work_order")
    return {
        "week_end": week_end,
        "due_week": open_orders.filter(due_date__gte=today, due_date__lte=week_end).count(),
        "overdue": open_orders.filter(due_date__lt=today).count(),
        "ship_week": CustomerOrder.objects.filter(ship_date__gte=today, ship_date__lte=week_end).count(),
        "ship_late": sum(1 for o in recent if order_state(o, today)[2]),
    }


def _bar(wo, win_start, win_end, ndays):
    """Geometry of one work order bar, clipped to the window."""
    bar_start = wo.start_date or wo.due_date
    bar_end = wo.due_date
    if bar_start > bar_end:
        bar_start, bar_end = bar_end, bar_start
    first = max(bar_start, win_start)
    last = min(bar_end, win_end)
    left = (first - win_start).days
    width = (last - first).days + 1
    inside = width * DAY_PX >= INSIDE_LABEL_PX
    near_end = ((left + width) * DAY_PX + INSIDE_LABEL_PX > ndays * DAY_PX
                and left * DAY_PX >= INSIDE_LABEL_PX)
    return {
        "left": left, "width": width, "clip_l": bar_start < win_start, "clip_r": bar_end > win_end,
        "label_pos": "in" if inside else "left" if near_end else "right",
        "no_start": wo.start_date is None,
    }


def timeline(request):
    today = date.today()
    p = Params.from_request(request.GET)

    win_start = _monday(today - timedelta(weeks=WEEKS_BACK)) + timedelta(weeks=p.shift)
    win_end = _monday(today + timedelta(weeks=p.weeks)) + timedelta(days=6, weeks=p.shift)
    ndays = (win_end - win_start).days + 1

    work_orders = WorkOrder.objects.select_related("product", "technician", "workstation").annotate(
        unit_count=Count("units")).prefetch_related("order_lines__order")
    if p.status == "open":
        work_orders = work_orders.exclude(status=WorkOrder.COMPLETE)
    elif p.status != "all":
        work_orders = work_orders.filter(status=p.status)
    if p.product:
        work_orders = work_orders.filter(product_id=p.product)
    if p.tech:
        work_orders = work_orders.filter(technician_id=p.tech)
    work_orders = work_orders.filter(Q(due_date__isnull=True) | Q(due_date__gte=win_start))

    scheduled, unscheduled = [], []
    for wo in work_orders:
        if wo.due_date is None:
            unscheduled.append(wo)
        elif (wo.start_date or wo.due_date) <= win_end:
            scheduled.append(wo)

    groups = {}
    for wo in scheduled:
        groups.setdefault(wo.product_id, []).append(wo)
    ordered_groups = sorted(groups.values(), key=lambda g: min((w.start_date or w.due_date, w.number) for w in g))

    rows = [{"type": "section", "title": "Build", "note": "work orders, start to due date"}]
    for group in ordered_groups:
        group.sort(key=lambda w: (w.start_date or w.due_date, w.due_date, w.number))
        product = group[0].product
        rows.append({"type": "group", "product": product, "count": len(group)})
        for wo in group:
            progress = 100 if wo.status == WorkOrder.COMPLETE else wo.progress_pct
            customers = _customers(wo)
            rows.append({
                "type": "wo", "wo": wo, "bar": _bar(wo, win_start, win_end, ndays), "progress": progress,
                "tip": _wo_tip(wo, customers), "orders": " ".join(sorted({
                    line.order.number for line in wo.order_lines.all()})),
            })
    if not ordered_groups:
        rows.append({"type": "empty", "text": "No work orders in this window for the selected filters."})

    customer_orders = CustomerOrder.objects.filter(ship_date__gte=win_start, ship_date__lte=win_end).prefetch_related(
        "lines__product", "lines__work_order__technician")
    ship_orders = [o for o in customer_orders if _order_matches(o, p, today)]
    ship_orders.sort(key=lambda o: (o.ship_date, o.number))
    rows.append({"type": "section", "title": "Ship", "note": "customer orders, diamond on ship date"})
    items = [_wo_item(wo) for wo in scheduled + unscheduled]
    for order in ship_orders:
        state, tone, late = order_state(order, today)
        linked = [line.work_order for line in order.lines.all() if line.work_order]
        due_dates = [wo.due_date for wo in linked if wo.due_date]
        conn = None
        if due_dates and max(due_dates) < order.ship_date:
            start = max(max(due_dates), win_start)
            conn = {"left": (start - win_start).days, "width": (order.ship_date - start).days}
        ship_idx = (order.ship_date - win_start).days
        lines = list(order.lines.all())
        unlinked = sum(1 for line in lines if not line.work_order_id)
        tip = _tip([
            f"Customer order {order.number}" + ("  (LATE)" if late else ""),
            order.customer,
            f"Ordered {order.order_date:%a %d %b %Y}  |  Ships {order.ship_date:%a %d %b %Y}",
            f"Status: {state}",
            "Lines: " + ", ".join(f"{line.product.code} x{line.quantity}" for line in lines),
            "Works orders: " + (", ".join(sorted({wo.number for wo in linked})) or "none raised"),
            f"{unlinked} line(s) with no works order raised" if unlinked and linked else "",
        ])
        rows.append({
            "type": "ship", "order": order, "state": state, "tone": tone, "late": late, "tip": tip,
            "idx": ship_idx, "conn": conn, "linked": sorted({wo.number for wo in linked}),
            "unlinked": unlinked, "label_left": ship_idx * DAY_PX + 200 > ndays * DAY_PX,
        })
        items.append(_order_item(order, state, tone))
    if not ship_orders:
        rows.append({"type": "empty", "text": "No shipments in this window for the selected filters."})

    columns = [
        Column("kind", "Type", lambda r: r.kind),
        Column("number", "Number", lambda r: r.number, url=lambda r: r.url, mono=True),
        Column("product", "Product", lambda r: r.product),
        Column("customer", "Customer", lambda r: r.customer),
        Column("start", "Start / ordered", lambda r: r.start),
        Column("end", "Due / ships", lambda r: r.end),
        Column("status", "Status", lambda r: r.status, pill=lambda r: r.tone),
        Column("tech", "Technician", lambda r: r.technician),
        Column("updated", "Updated", lambda r: r.updated, fmt="datetime"),
    ]
    table, csv_response = build_table(request, columns, items, filename="planning-timeline",
                                      default_sort="end")
    if csv_response:
        return csv_response

    days = [win_start + timedelta(days=i) for i in range(ndays)]
    weeks = [{"start": days[i], "label": f"{days[i].day} {days[i]:%b}"} for i in range(0, ndays, 7)]
    base = Params(product=p.product, tech=p.tech, status=p.status, weeks=p.weeks)
    return render(request, "mes/planning/timeline.html", {
        "p": p, "rows": rows, "days": days, "weeks": weeks, "ndays": ndays, "today": today,
        "today_idx": (today - win_start).days if win_start <= today <= win_end else None,
        "day_px": DAY_PX, "label_px": LABEL_PX, "track_px": ndays * DAY_PX,
        "win_start": win_start, "win_end": win_end, "kpi": _kpis(today), "table": table,
        "unscheduled": unscheduled,
        "products": Product.objects.filter(workorder__isnull=False).distinct().order_by("code"),
        "technicians": ProductionTechnician.objects.order_by("name"),
        "status_filters": STATUS_FILTERS, "week_choices": WEEK_CHOICES,
        "prev_url": base.query(shift=p.shift - 4), "next_url": base.query(shift=p.shift + 4),
        "today_url": base.query(), "item_count": len(items),
    })
