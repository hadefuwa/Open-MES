"""Reusable data table: search, sortable columns, pagination and CSV export.

Usage in a view:

    columns = [
        Column("code", "Code", "code", url=lambda p: p.get_absolute_url(), mono=True),
        Column("name", "Name", "name"),
        Column("cost", "Cost", lambda p: p.total_cost, numeric=True, fmt="money"),
        Column("created", "Created", "created_at", fmt="datetime"),
        Column("status", "Status", "status", pill=lambda p: "ok" if p.ok else "bad"),
    ]
    table, csv_response = build_table(request, columns, queryset, filename="products")
    if csv_response:
        return csv_response
    return render(request, "mes/products.html", {"table": table})

and in the template:  {% include "mes/_table.html" %}

Rows can be a queryset or a list. Extra GET parameters (your own filters) are preserved by the
sort, paging and CSV links. `?format=csv` returns every matching row as a CSV download.
"""
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone


@dataclass
class Column:
    key: str
    label: str
    value: object                 # attribute path ("product.code") or callable(row) -> value
    url: object = None            # callable(row) -> url or None  (renders the cell as a link)
    pill: object = None           # callable(row) -> "ok" | "warn" | "bad" | "info" | None
    numeric: bool = False         # right-align and sort numerically
    mono: bool = False            # monospace "code" style
    fmt: str = ""                 # "", "money", "datetime", "date", "minutes"
    sortable: bool = True


@dataclass
class Cell:
    text: str
    url: str = ""
    pill: str = ""
    mono: bool = False
    numeric: bool = False


def _get(row, accessor):
    if callable(accessor):
        return accessor(row)
    obj = row
    for part in accessor.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
        if callable(obj):
            obj = obj()
    return obj


def _text(value, fmt):
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return value.strftime("%d %b %Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    if fmt == "money" and isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
        if amount and abs(amount) < Decimal("0.1"):  # tiny parts (resistors, screws) need the extra digits
            return f"£{amount:.4f}"
        return f"£{amount:,.2f}"
    if fmt == "minutes" and isinstance(value, (int, float, Decimal)):
        return f"{Decimal(value):,.0f} min"
    if fmt == "percent" and isinstance(value, (int, float, Decimal)):
        return f"{Decimal(str(value)):.1f}%"
    if isinstance(value, Decimal):
        return f"{value.normalize():f}" if value == value.to_integral() else f"{value:.2f}"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return (timezone.localtime(value) if timezone.is_aware(value) else value).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return value


def _sort_key(value, numeric):
    if value is None or value == "":
        return (1, 0, "")
    if numeric or isinstance(value, (int, float, Decimal)):
        return (0, float(value), "")
    if isinstance(value, (date, datetime)):
        return (0, value.timestamp() if isinstance(value, datetime) else value.toordinal(), "")
    return (0, 0, str(value).lower())


class Table:
    def __init__(self, columns, cells, total, page, q, sort, desc, base_params, filename):
        self.columns = columns
        self.rows = cells
        self.total = total
        self.page = page
        self.q = q
        self.sort = sort
        self.desc = desc
        self._base = base_params
        self.filename = filename

    def _url(self, **over):
        params = dict(self._base)
        params.update({k: v for k, v in over.items() if v not in (None, "")})
        for k in [k for k, v in over.items() if v in (None, "")]:
            params.pop(k, None)
        return "?" + urlencode(params) if params else "?"

    @property
    def csv_url(self):
        return self._url(format="csv")

    @property
    def headers(self):
        out = []
        for col in self.columns:
            active = self.sort == col.key
            out.append({
                "label": col.label, "numeric": col.numeric, "sortable": col.sortable, "active": active,
                "desc": active and self.desc,
                "url": self._url(sort=col.key, dir="asc" if (active and self.desc) or not active else "desc",
                                 page=None),
            })
        return out

    @property
    def prev_url(self):
        return self._url(page=self.page.number - 1) if self.page.has_previous() else ""

    @property
    def next_url(self):
        return self._url(page=self.page.number + 1) if self.page.has_next() else ""


def build_table(request, columns, rows, filename="export", per_page=50, default_sort=None, default_desc=False):
    """Returns (table, csv_response). csv_response is None unless ?format=csv was requested."""
    get = request.GET
    q = get.get("q", "").strip()
    sort = get.get("sort") or default_sort
    desc = (get.get("dir") == "desc") if get.get("sort") else default_desc

    rows = list(rows)
    if q:
        needle = q.lower()
        rows = [r for r in rows if any(needle in _text(_get(r, c.value), c.fmt).lower() for c in columns)]
    by_key = {c.key: c for c in columns}
    if sort in by_key:
        col = by_key[sort]
        rows.sort(key=lambda r: _sort_key(_get(r, col.value), col.numeric), reverse=desc)

    if get.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow([c.label for c in columns])
        for r in rows:
            writer.writerow([_csv_value(_get(r, c.value)) for c in columns])
        return None, response

    page = Paginator(rows, per_page).get_page(get.get("page"))
    cells = []
    for r in page.object_list:
        row = []
        for c in columns:
            value = _get(r, c.value)
            row.append(Cell(text=_text(value, c.fmt), url=(c.url(r) or "") if c.url else "",
                            pill=(c.pill(r) or "") if c.pill else "", mono=c.mono, numeric=c.numeric))
        cells.append(row)
    base = {k: v for k, v in get.items() if k not in ("page", "format")}
    return Table(columns, cells, len(rows), page, q, sort, desc, base, filename), None
