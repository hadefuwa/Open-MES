"""Data packs: self-contained datasets that `manage.py seed` loads.

The software is generic; everything specific to a business lives in a pack, a module in this package
selected with `--pack NAME` or the MES_DATA_PACK setting (default: generic). A pack is plain data plus,
optionally, a loader for real files. Attributes (all but the first block are optional):

  Required catalogue data
    TECHNICIANS      list of names
    STATIONS         list of workstation names
    FINISHED, ASSEMBLIES   [(code, name)]
    COMPONENTS       [(code, name, category, unit cost)]
    BOM              {parent code: [(child code, quantity)]}
    MACHINES         [(name, kind, status, location, notes)]      status: available | in_use | maintenance | down
    ROUTINGS         {product code: [(step name, machine name or None, minutes)]}
    RRP              {finished product code: recommended retail price}   (optional)

  Demo activity (omit for a pack that should hold real data only)
    LIVE_ORDERS      [(number, product, qty, station, due in N days, status, technician or None, est minutes)]
    HISTORY_PRODUCTS products built in the two-week history, HISTORY_STATIONS, HISTORY_START_NUMBER
    CUSTOMER_ORDERS  [(number, days ago, customer, ref, [(product, qty)])]
    HOOKS            area hooks to run, from: catalogue, planning, machines, defects
    BEST_SELLERS, CUSTOMERS, PLANNING_ORDERS, STOCK_BUILDS, MACHINE_NOTES   inputs to those hooks

  Real data
    load_real_data(command)   import workbooks etc.; runs before classification and costing
    CALIBRATE_TO_RRP          True to tie BOM cost to a third of RRP after a price list import
"""
import importlib

from django.conf import settings


def load_pack(name=None):
    name = name or getattr(settings, "MES_DATA_PACK", "generic")
    return importlib.import_module(f"mes.datapacks.{name}")


HOOK_NAMES = {"catalogue", "planning", "machines", "defects", "testreports"}


def check_pack(pack):
    """Return a list of problems with a pack's data (empty when it is consistent). Catches typos in codes,
    machine, station and technician names before they turn into confusing errors halfway through a seed."""
    problems = []
    finished = [c for c, _ in getattr(pack, "FINISHED", [])]
    assemblies = [c for c, _ in getattr(pack, "ASSEMBLIES", [])]
    components = [row[0] for row in getattr(pack, "COMPONENTS", [])]
    codes = finished + assemblies + components
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        problems.append(f"duplicate product code {code}")
    known = set(codes)
    machines = {m[0] for m in getattr(pack, "MACHINES", [])}
    stations, technicians = set(getattr(pack, "STATIONS", [])), set(getattr(pack, "TECHNICIANS", []))

    def need(code, where):
        if code not in known:
            problems.append(f"{where}: unknown product {code}")

    for parent, lines in getattr(pack, "BOM", {}).items():
        need(parent, "BOM parent")
        for child, qty in lines:
            need(child, f"BOM line under {parent}")
            if qty <= 0:
                problems.append(f"BOM line {parent} > {child} has quantity {qty}")
    for code, steps in getattr(pack, "ROUTINGS", {}).items():
        need(code, "ROUTINGS")
        for step, machine, _minutes in steps:
            if machine and machine not in machines:
                problems.append(f"ROUTINGS {code} step '{step}': unknown machine {machine}")
    for code in getattr(pack, "RRP", {}):
        need(code, "RRP")
    for number, code, _q, station, _d, status, tech, _m in getattr(pack, "LIVE_ORDERS", []):
        need(code, f"LIVE_ORDERS {number}")
        if station not in stations:
            problems.append(f"LIVE_ORDERS {number}: unknown station {station}")
        if tech and tech not in technicians:
            problems.append(f"LIVE_ORDERS {number}: unknown technician {tech}")
        if status not in ("entered", "allocated", "issued", "in_progress", "qa", "complete"):
            problems.append(f"LIVE_ORDERS {number}: unknown status {status}")
    for code in getattr(pack, "HISTORY_PRODUCTS", []):
        need(code, "HISTORY_PRODUCTS")
    for number, _ago, _customer, _ref, lines in getattr(pack, "CUSTOMER_ORDERS", []):
        for code, _qty in lines:
            need(code, f"CUSTOMER_ORDERS {number}")
    for number, _ago, _customer, _ship, lines in getattr(pack, "PLANNING_ORDERS", []):
        for spec in lines:
            need(spec[0], f"PLANNING_ORDERS {number}")
            if len(spec) > 4 and spec[4] and spec[4] not in technicians:
                problems.append(f"PLANNING_ORDERS {number}: unknown technician {spec[4]}")
    for code, _q, _status, _due, tech in getattr(pack, "STOCK_BUILDS", []):
        need(code, "STOCK_BUILDS")
        if tech and tech not in technicians:
            problems.append(f"STOCK_BUILDS {code}: unknown technician {tech}")
    for code in getattr(pack, "BEST_SELLERS", {}):
        need(code, "BEST_SELLERS")
    for name in getattr(pack, "MACHINE_NOTES", {}):
        if name not in machines:
            problems.append(f"MACHINE_NOTES: unknown machine {name}")
    for hook in getattr(pack, "HOOKS", ()):
        if hook not in HOOK_NAMES:
            problems.append(f"HOOKS: unknown hook {hook}")
    return problems
