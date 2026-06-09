from django.contrib import admin
from .models import ReservaEvento, ReservaServicio, Pago, Alquiler, AlquilerProducto, Lugar, MenuComida, ReservaProducto, EvaluacionEvento

# Register your models here.

admin.site.register(ReservaEvento)
admin.site.register(ReservaServicio)
admin.site.register(ReservaProducto)
admin.site.register(Alquiler)
admin.site.register(AlquilerProducto)
admin.site.register(Pago)
admin.site.register(EvaluacionEvento)
admin.site.register(MenuComida)
admin.site.register(Lugar)