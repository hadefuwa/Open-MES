from datetime import datetime, time, timedelta

from django.utils import timezone

from mes.models import CustomerOrder, CustomerOrderLine, Product

def seed(ctx):
    """Thirty historical customer orders over the past year. Customers and best sellers come from the pack."""
    rng = ctx.rng
    customers, best_sellers = ctx.pack.CUSTOMERS, ctx.pack.BEST_SELLERS
    finished = [p for p in ctx.products.values() if p.kind == Product.FINISHED]
    weights = [best_sellers.get(p.code, 1) for p in finished]

    for i in range(30):
        order_date = ctx.today - timedelta(days=rng.randint(20, 365))
        ship_date = order_date + timedelta(days=rng.randint(7, 30))
        number = str(21001 + i * 3 + rng.randint(0, 2))
        order = CustomerOrder.objects.create(
            number=number, order_date=order_date, ship_date=ship_date,
            customer=rng.choice(customers), customer_ref=f"PO-{rng.randint(10000, 99999)}",
            created_at=_stamp(order_date), updated_at=_stamp(ship_date))
        picked = []
        for _ in range(rng.randint(1, 4)):
            product = rng.choices(finished, weights)[0]
            if product in picked:
                continue
            picked.append(product)
            qty = rng.choice([2, 3, 5, 5, 10, 10, 15, 20]) if best_sellers.get(product.code, 0) >= 6 \
                else rng.choice([1, 2, 3, 5])
            CustomerOrderLine.objects.create(order=order, product=product, quantity=qty)
        CustomerOrder.objects.filter(pk=order.pk).update(updated_at=_stamp(ship_date))
        order.lines.update(created_at=_stamp(order_date), updated_at=_stamp(order_date))


def _stamp(day):
    return timezone.make_aware(datetime.combine(day, time(9, 30)))
