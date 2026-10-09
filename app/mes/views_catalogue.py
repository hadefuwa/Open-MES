from django.db.models import Count, Max, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import costing
from .models import CustomerOrderLine, Product, Unit, WorkOrder
from .tables import Column, build_table


def _product_url(p):
    return p.get_absolute_url()


def _cost_columns():
    return [
        Column("build", "Build time", lambda p: p.build_minutes, numeric=True, fmt="minutes"),
        Column("bom", "BOM cost", lambda p: p.bom_cost, numeric=True, fmt="money"),
        Column("total", "Total cost to manufacture", lambda p: p.total_cost, numeric=True, fmt="money"),
    ]


def _stamp_columns():
    return [
        Column("created", "Created", "created_at", fmt="datetime"),
        Column("updated", "Updated", "updated_at", fmt="datetime"),
    ]


def _average(values):
    values = list(values)
    return sum(values) / len(values) if values else 0


def _margin_pill(p):
    if p.margin_pct_cached is None:
        return None
    return "ok" if p.margin_pct_cached >= 50 else "warn" if p.margin_pct_cached >= 30 else "bad"


def products(request):
    base = Product.objects.filter(kind=Product.FINISHED)
    ranges = list(base.exclude(range_name="").values("range_name").annotate(n=Count("id")).order_by("range_name"))
    selected = request.GET.get("range", "")
    rows = list(base.filter(range_name=selected) if selected else base)
    last_built = dict(Unit.objects.values_list("work_order__product_id").annotate(m=Max("created_at")))
    sold = dict(CustomerOrderLine.objects.values_list("product_id").annotate(s=Sum("quantity")))
    for p in rows:
        p.last_built = last_built[p.pk].date() if last_built.get(p.pk) else None
        p.units_sold = sold.get(p.pk, 0)
        p.cost_total = p.total_cost
        p.margin_pct_cached = (round(100 * (p.rrp - p.cost_total) / p.rrp, 1) if p.rrp else None)

    columns = [
        Column("code", "Code", "code", url=_product_url, mono=True),
        Column("name", "Name", "name"),
        Column("range", "Range", "range_name"),
        Column("rrp", "RRP", "rrp", numeric=True, fmt="money", pill=lambda p: "warn" if p.rrp_estimated else None),
        Column("bom", "BOM cost", lambda p: p.bom_cost, numeric=True, fmt="money"),
        Column("build", "Build time", lambda p: p.build_minutes, numeric=True, fmt="minutes"),
        Column("total", "Total cost to manufacture", "cost_total", numeric=True, fmt="money"),
        Column("margin", "Margin", "margin_pct_cached", numeric=True, fmt="percent", pill=_margin_pill),
        Column("last_built", "Last built", "last_built", fmt="date"),
        Column("sold", "Units sold", "units_sold", numeric=True),
        *_stamp_columns(),
    ]
    table, csv_response = build_table(request, columns, rows, filename="products", default_sort="code")
    if csv_response:
        return csv_response
    priced = [p for p in rows if p.rrp]
    stats = {"count": len(rows), "avg_cost": _average(p.cost_total for p in rows),
             "avg_rrp": _average(p.rrp for p in priced),
             "sold": sum(p.units_sold for p in rows),
             "best": max(rows, key=lambda p: p.units_sold, default=None)}
    chips = [{"name": r["range_name"], "n": r["n"], "active": r["range_name"] == selected} for r in ranges]
    return render(request, "mes/catalogue/products.html", {
        "table": table, "stats": stats, "chips": chips, "selected": selected,
        "all_count": base.count()})


def assemblies(request):
    rows = list(Product.objects.filter(kind=Product.ASSEMBLY)
                .annotate(parents=Count("used_in__parent", distinct=True)))
    columns = [
        Column("code", "Code", "code", url=_product_url, mono=True),
        Column("name", "Name", "name"),
        Column("category", "Category", "category"),
        Column("parents", "Used in", "parents", numeric=True),
        *_cost_columns(),
        *_stamp_columns(),
    ]
    table, csv_response = build_table(request, columns, rows, filename="assemblies", default_sort="code")
    if csv_response:
        return csv_response
    stats = {"count": len(rows), "avg_cost": _average(p.total_cost for p in rows),
             "used": sum(1 for p in rows if p.parents)}
    return render(request, "mes/catalogue/assemblies.html", {"table": table, "stats": stats})


def components(request):
    base = Product.objects.filter(kind=Product.COMPONENT)
    categories = list(base.values("category").annotate(n=Count("id")).order_by("category"))
    selected = request.GET.get("category", "")
    qs = base.filter(category=selected) if selected else base
    rows = list(qs.annotate(uses=Count("used_in")))
    columns = [
        Column("code", "Code", "code", url=_product_url, mono=True),
        Column("name", "Name", "name"),
        Column("category", "Category", "category"),
        Column("cost", "Unit cost", "unit_cost", numeric=True, fmt="money"),
        Column("rrp", "Spare RRP", "rrp", numeric=True, fmt="money"),
        Column("stock", "Free stock", "free_stock", numeric=True,
               pill=lambda p: "bad" if p.low_stock else None),
        Column("reorder", "Re-order level", "reorder_level", numeric=True),
        Column("supplier", "Supplier", "supplier_code"),
        Column("uses", "Used in", "uses", numeric=True),
        *_stamp_columns(),
    ]
    table, csv_response = build_table(request, columns, rows, filename="components", default_sort="code")
    if csv_response:
        return csv_response
    chips = [{"category": c["category"], "n": c["n"], "active": c["category"] == selected} for c in categories]
    return render(request, "mes/catalogue/components.html", {
        "table": table, "chips": chips, "selected": selected, "all_count": base.count(),
        "stats": {"count": len(rows), "avg_cost": _average(p.unit_cost or 0 for p in rows),
                  "low_stock": sum(1 for p in rows if p.low_stock),
                  "used": sum(1 for p in rows if p.uses)},
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.kind == Product.COMPONENT:
        return redirect("component_detail", pk=product.pk)

    sales_qs = (CustomerOrderLine.objects.filter(product=product).select_related("order")
                .order_by("-order__order_date", "-order__number"))
    sales_columns = [
        Column("date", "Order date", "order.order_date", fmt="date"),
        Column("customer", "Customer", "order.customer"),
        Column("order", "Order", "order.number", url=lambda l: _order_url(l.order), mono=True),
        Column("qty", "Quantity", "quantity", numeric=True),
        Column("ship", "Ship date", "order.ship_date", fmt="date"),
    ]
    sales, csv_response = build_table(request, sales_columns, sales_qs, filename=f"{product.code}-sales",
                                      per_page=10)
    if csv_response:
        return csv_response

    work_orders = list(WorkOrder.objects.filter(product=product).order_by("-start_date", "-created_at")[:8])
    units = list(Unit.objects.filter(work_order__product=product).select_related("work_order")
                 .order_by("-created_at")[:10])
    labour = costing.labour_cost(product)
    bom_cost = costing.bom_cost(product)
    return render(request, "mes/catalogue/product_detail.html", {
        "product": product,
        "has_bom": product.bom_lines.exists(),
        "build_minutes": costing.total_build_minutes(product),
        "bom_cost": bom_cost,
        "labour_cost": labour,
        "total_cost": bom_cost + labour,
        "labour_rate": costing.labour_rate(),
        "sales": sales,
        "units_sold": sales_qs.aggregate(s=Sum("quantity"))["s"] or 0,
        "work_orders": work_orders,
        "units": units,
    })


def _order_url(order):
    return reverse("customer_order", args=[order.pk])
