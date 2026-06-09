from django.contrib import admin
from .models import Producto, MovimientoProducto

# Register your models here.

admin.site.register(Producto)
admin.site.register(MovimientoProducto)