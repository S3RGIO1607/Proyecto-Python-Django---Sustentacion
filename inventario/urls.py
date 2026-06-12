# inventario/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # //////////// VISTA PÚBLICA (CLIENTE) ////////////
    path('catalogo/', views.productos_catalogo, name="productos_catalogo"),

    # //////////// GESTIÓN DE PRODUCTOS (STAFF) ////////////
    path('productos/', views.listar_productos, name='listar_productos'),
    path('productos/crear/', views.mostrar_registro_producto, name='mostrar_registro_producto'),
    path('productos/registrar/', views.registrar_producto, name='registrar_producto'),
    path('productos/detalle/<int:id>/', views.mostrar_detalle_producto, name='mostrar_detalle_producto'),
    path('productos/pre-editar/<int:id>/', views.pre_editar_producto, name='pre_editar_producto'),
    path('productos/actualizar/', views.editar_producto, name='editar_producto'),
    path('productos/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),
    path('productos/habilitar/<int:id>/', views.habilitar_producto, name='habilitar_producto'),

    # //////////// REPORTES Y MOVIMIENTOS ////////////
    path('productos/reporte-pdf/', views.exportar_productos_pdf, name='exportar_productos_pdf'),
    path('productos/movimientos/', views.listar_movimientos, name='movimientos_producto'),
    path('productos/movimientos/registrar/', views.interfaz_registro_manual, name='interfaz_registro_manual'),
    path('productos/movimientos/registrar-manual/', views.registrar_movimiento_manual, name='registrar_movimiento_manual'),

    # //////////// SUPER CARGA DESDE CSV ////////////
    path('super-carga/', views.ejecutar_super_carga, name='ejecutar_super_carga'),
]