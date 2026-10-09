"""Data browser: every table in the database as a web page, with row counts, relationships
and CSV export. Foreign keys are links, so the whole relational model can be walked."""
from django.apps import apps
from django.db.models import Max
from django.http import Http404
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from .tables import Column, build_table

# Plain-English description of each table, shown on the browser index.
DESCRIPTIONS = {
    "Product": "Finished products, sub-assemblies and components (one catalogue table)",
    "BomLine": "Bill of materials: which item is made from how many of which other items",
    "RoutingStep": "Manufacturing operations per product, with the machine each needs",
    "Machine": "Machinery and its availability",
    "Workstation": "Work areas on the shop floor",
    "ProductionTechnician": "People who build and test products",
    "WorkOrder": "Production jobs, from entry to completion",
    "Unit": "Individual serialised units built under work orders",
    "Event": "Append-only audit trail of everything that happens to a work order",
    "CustomerOrder": "Customer orders with order and ship dates",
    "CustomerOrderLine": "Products and quantities on each customer order",
    "Defect": "Recorded defects and scrap with the part, the build and the cost",
    "TestReport": "Completed test procedures for built units",
    "TestStep": "Individual steps and results within each test report",
}
# Where each table has a friendlier page of its own.
FRIENDLY = {
    "Product": "products", "Machine": "machines", "WorkOrder": "board", "CustomerOrder": "customer_orders",
    "Defect": "defects", "TestReport": "test_reports",
}


def object_url(obj):
    """URL of the page that shows `obj`, or "" when it has none."""
    if obj is None:
        return ""
    name = type(obj).__name__
    try:
        if name == "Product":
            return obj.get_absolute_url()
        if name == "WorkOrder":
            return reverse("operator", args=[obj.pk])
        if name == "CustomerOrder":
            return reverse("customer_order", args=[obj.pk])
        if name == "Machine":
            return reverse("machine_detail", args=[obj.pk])
        if name == "TestReport":
            return reverse("test_report", args=[obj.pk])
        if name == "ProductionTechnician":
            return f"{reverse('my_jobs')}?technician={obj.pk}"
        if name == "Unit":
            return f"{reverse('traceability')}?serial={obj.serial}"
        if name == "CustomerOrderLine":
            return reverse("customer_order", args=[obj.order_id])
        if name in ("BomLine", "RoutingStep"):
            return reverse("bom", args=[obj.parent_id if name == "BomLine" else obj.product_id])
        if name in ("TestStep",):
            return reverse("test_report", args=[obj.report_id])
        if name in ("Event", "Defect"):
            return reverse("operator", args=[obj.work_order_id]) if obj.work_order_id else ""
    except NoReverseMatch:
        return ""
    return ""


def _models():
    return [m for m in apps.get_app_config("mes").get_models()]


def _stamp_field(model):
    names = {f.name for f in model._meta.concrete_fields}
    for candidate in ("updated_at", "timestamp", "occurred_at", "created_at"):
        if candidate in names:
            return candidate
    return None


def data_browser(request):
    tables = []
    for model in sorted(_models(), key=lambda m: m.__name__):
        stamp = _stamp_field(model)
        last = model.objects.aggregate(last=Max(stamp))["last"] if stamp else None
        relations = [
            {"name": f.related_model.__name__, "field": f.name}
            for f in model._meta.concrete_fields if f.is_relation
        ]
        tables.append({
            "name": model.__name__, "label": model._meta.verbose_name_plural.title(),
            "rows": model.objects.count(), "fields": len(model._meta.concrete_fields),
            "last": last, "relations": relations, "description": DESCRIPTIONS.get(model.__name__, ""),
            "friendly": FRIENDLY.get(model.__name__),
        })
    return render(request, "mes/data/data_browser.html", {
        "tables": tables, "total_rows": sum(t["rows"] for t in tables),
        "total_links": sum(len(t["relations"]) for t in tables),
    })


def data_table(request, model_name):
    model = next((m for m in _models() if m.__name__.lower() == model_name.lower()), None)
    if model is None:
        raise Http404("No such table")

    fields = list(model._meta.concrete_fields)
    columns = []
    for f in fields:
        if f.is_relation:
            columns.append(Column(f.name, f.name.replace("_", " ").title(),
                                  lambda r, n=f.name: getattr(r, n),
                                  url=lambda r, n=f.name: object_url(getattr(r, n))))
        elif f.choices:
            columns.append(Column(f.name, f.verbose_name.title(),
                                  lambda r, n=f.name: getattr(r, f"get_{n}_display")()))
        else:
            fmt = "datetime" if f.get_internal_type() == "DateTimeField" else ""
            columns.append(Column(f.name, f.verbose_name.title() if f.name != "id" else "ID", f.name, fmt=fmt,
                                  numeric=f.get_internal_type() in ("DecimalField", "IntegerField", "BigAutoField",
                                                                    "PositiveIntegerField", "FloatField")))
    related = [f.name for f in fields if f.is_relation]
    qs = model.objects.select_related(*related) if related else model.objects.all()
    table, csv_response = build_table(request, columns, qs.order_by("-pk"), filename=model.__name__.lower(),
                                      per_page=50)
    if csv_response:
        return csv_response
    return render(request, "mes/data/data_table.html", {
        "table": table, "model": model.__name__, "label": model._meta.verbose_name_plural.title(),
        "description": DESCRIPTIONS.get(model.__name__, ""), "friendly": FRIENDLY.get(model.__name__),
        "relations": [{"name": f.related_model.__name__, "field": f.name} for f in fields if f.is_relation],
        "reverse": [{"name": r.related_model.__name__, "field": r.field.name}
                    for r in model._meta.related_objects],
    })
