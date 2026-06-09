from django.contrib import admin
from .models import Paquete, PaqueteProducto, PaqueteServicio, Servicio

# Register your models here.

admin.site.register(Servicio)
admin.site.register(Paquete)
admin.site.register(PaqueteProducto)
admin.site.register(PaqueteServicio)