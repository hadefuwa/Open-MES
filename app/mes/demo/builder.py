"""Turn a data pack's catalogue lists into database rows."""
from decimal import Decimal as D

from mes.models import BomLine, Machine, Product, RoutingStep


def build_catalogue(pack):
    """Create products, BOMs, machines and routings from a pack. Returns (products, machines) by code/name."""
    rrp = getattr(pack, "RRP", {})
    products = {}
    for code, name in pack.FINISHED:
        products[code] = Product.objects.create(code=code, name=name, kind=Product.FINISHED,
                                                rrp=D(str(rrp[code])) if code in rrp else None)
    for code, name in pack.ASSEMBLIES:
        products[code] = Product.objects.create(code=code, name=name, kind=Product.ASSEMBLY)
    for code, name, category, cost in pack.COMPONENTS:
        products[code] = Product.objects.create(code=code, name=name, kind=Product.COMPONENT,
                                                category=category, unit_cost=D(str(cost)))

    for parent, lines in pack.BOM.items():
        for seq, (child, qty) in enumerate(lines, start=1):
            BomLine.objects.create(parent=products[parent], child=products[child], quantity=D(str(qty)),
                                   sequence=seq * 10)

    machines = {}
    for name, kind, status, location, notes in pack.MACHINES:
        machines[name] = Machine.objects.create(name=name, kind=kind, status=status, location=location,
                                                notes=notes)

    for code, steps in pack.ROUTINGS.items():
        for seq, (step, machine, minutes) in enumerate(steps, start=1):
            RoutingStep.objects.create(product=products[code], sequence=seq * 10, name=step,
                                       machine=machines.get(machine), minutes=D(str(minutes)))
    return products, machines
