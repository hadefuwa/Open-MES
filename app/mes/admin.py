from django.contrib import admin

from .models import (CustomerOrder, CustomerOrderLine, Event, ProductionTechnician, Product, Unit,
                     WorkOrder, Workstation)

admin.site.register(Product)
admin.site.register(ProductionTechnician)
admin.site.register(Workstation)
admin.site.register(WorkOrder)
admin.site.register(Unit)
admin.site.register(Event)
admin.site.register(CustomerOrder)
admin.site.register(CustomerOrderLine)
