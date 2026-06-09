# paquetes/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # //////////// VISTA PÚBLICA (CLIENTE) ////////////
    path('catalogo/', views.paquetes_catalogo, name="paquetes_catalogo"),

    # //////////// GESTIÓN DE PAQUETES (STAFF) ////////////
    path('admin/paquetes/', views.listar_paquetes, name='listar_paquetes'),
    path('admin/paquetes/crear/', views.mostrar_registro_paquete, name='mostrar_registro_paquete'),
    path('admin/paquetes/registrar/', views.registrar_paquete, name='registrar_paquete'),
    path('admin/paquetes/detalle/<int:id>/', views.mostrar_detalle_paquete, name='mostrar_detalle_paquete'),
    path('admin/paquetes/pre-editar/<int:id>/', views.pre_editar_paquete, name='pre_editar_paquete'),
    path('admin/paquetes/editar/<int:id>/', views.editar_paquete, name='editar_paquete'),
    path('admin/paquetes/eliminar/<int:id>/', views.eliminar_paquete, name='eliminar_paquete'),
    path('admin/paquetes/activar/<int:id>/', views.activar_paquete, name='activar_paquete'),

    # //////////// GESTIÓN DE SERVICIOS (STAFF) ////////////
    path('admin/servicios/crear/', views.mostrar_registro_servicio, name='mostrar_registro_servicio'),
    path('admin/servicios/registrar/', views.registrar_servicio, name='registrar_servicio'),
    path('admin/servicios/pre-editar/<int:id>/', views.pre_editar_servicio, name='pre_editar_servicio'),
    path('admin/servicios/actualizar/', views.editar_servicio, name='editar_servicio'),
    path('admin/servicios/eliminar/<int:id>/', views.eliminar_servicio, name='eliminar_servicio'),
    path('admin/servicios/habilitar/<int:id>/', views.habilitar_servicio, name='habilitar_servicio'),
]