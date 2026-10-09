import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import bom as bomlib
from . import costing
from .models import Product
from .tables import Column, build_table


def _bom_url(product):
    return reverse("bom", args=[product.pk])


def _explosion_csv(product, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="bom-{product.code}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Level", "Code", "Name", "Kind", "Qty per parent", "Extended qty",
                     "Unit cost", "Line cost", "Extended cost", "Build minutes"])
    for r in rows:
        writer.writerow([r.level, r.child.code, r.child.name, r.child.get_kind_display(), r.quantity,
                         r.ext_quantity, f"{r.unit_cost:.2f}", f"{r.line_cost:.2f}", f"{r.ext_cost:.2f}",
                         r.minutes])
    return response


def bom(request, pk):
    product = get_object_or_404(Product, pk=pk)
    view = "flat" if request.GET.get("view") == "flat" else "tree"
    rows = bomlib.explode(product)
    if view == "tree" and request.GET.get("format") == "csv":
        return _explosion_csv(product, rows)

    flat = bomlib.flat_components(product)
    table = None
    if view == "flat":
        columns = [
            Column("code", "Code", "product.code", url=lambda f: f.product.get_absolute_url(), mono=True),
            Column("name", "Name", "product.name"),
            Column("category", "Category", "product.category"),
            Column("qty", "Total qty", "quantity", numeric=True),
            Column("unit", "Unit cost", "unit_cost", numeric=True, fmt="money"),
            Column("cost", "Total cost", "cost", numeric=True, fmt="money"),
            Column("used", "BOM lines", "used_in", numeric=True),
        ]
        table, csv_response = build_table(request, columns, flat, filename=f"components-{product.code}",
                                          default_sort="code")
        if csv_response:
            return csv_response

    labour = costing.labour_cost(product)
    material = costing.bom_cost(product)
    context = {
        "product": product, "rows": rows, "view": view, "table": table,
        "material": material, "labour": labour, "total": material + labour,
        "minutes": costing.total_build_minutes(product), "labour_rate": costing.labour_rate(),
        "component_count": len(flat), "max_level": max((r.level for r in rows), default=0),
        "assembly_count": sum(1 for r in rows if r.is_assembly),
        "where_used": [w for w in bomlib.where_used_all(product) if w.is_finished],
    }
    return render(request, "mes/bom/bom.html", context)


def component_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    direct = bomlib.where_used_direct(product)
    ancestors = bomlib.where_used_all(product)

    def path_text(w):
        return "; ".join(" > ".join(p.code for p in path) for path in w.paths)

    columns = [
        Column("code", "Used in", "product.code", url=lambda w: w.product.get_absolute_url(), mono=True),
        Column("name", "Name", "product.name"),
        Column("kind", "Type", lambda w: w.product.get_kind_display(),
               pill=lambda w: "ok" if w.is_finished else "info"),
        Column("qty", "Qty per unit", "quantity", numeric=True),
        Column("paths", "Path", path_text, sortable=False),
    ]
    table, csv_response = build_table(request, columns, ancestors, filename=f"where-used-{product.code}",
                                      default_sort="code")
    if csv_response:
        return csv_response
    return render(request, "mes/bom/component.html", {
        "product": product, "direct": direct, "table": table, "ancestor_count": len(ancestors),
        "finished_count": sum(1 for w in ancestors if w.is_finished),
    })
