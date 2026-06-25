# operaciones/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # //////////// INTERFAZ DEL CLIENTE (CARRITO Y MIS EVENTOS) ////////////
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_carrito, name='actualizar_carrito'),
    path('carrito/eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('carrito/confirmar/', views.confirmar_alquiler_carrito, name='confirmar_alquiler_carrito'),
    
    path('mis-reservas/', views.mis_reservas, name="mis_reservas"),
    path('reserva/nueva/<int:paquete_id>/', views.crear_reserva_cliente, name="crear_reserva_cliente"),
    path('reserva/detalle/<int:reserva_id>/', views.detalle_reserva, name="detalle_reserva"),
    path('reserva/cancelar/<int:reserva_id>/', views.cancelar_reserva_cliente, name='cancelar_reserva_cliente'),
    path('reserva/reprogramar/<int:reserva_id>/', views.reprogramar_reserva_cliente, name='reprogramar_reserva_cliente'),
    path('comprobante/<str:tipo>/<int:obj_id>/', views.descargar_comprobante_pdf, name='descargar_comprobante'),
    path('alquiler/detalle/<int:id>/', views.detalle_alquiler, name='detalle_alquiler'),
    path('pago/registrar/<str:tipo>/<int:id_objeto>/', views.registrar_pago_cliente, name='registrar_pago_cliente'),

    # //////////// GESTIÓN DE ALQUILERES (STAFF/BODEGA) ////////////
    path('admin/alquileres/', views.listar_alquileres, name='listar_alquileres'),
    path('admin/alquileres/detalle/<int:id>/', views.mostrar_detalle_alquiler, name='mostrar_detalle_alquiler'),
    path('admin/alquileres/despachar/<int:id>/', views.despachar_alquiler, name='despachar_alquiler'),
    path('admin/alquileres/retorno/<int:id>/', views.registrar_retorno, name='registrar_retorno'),
    path('admin/alquileres/liquidar/<int:id>/', views.liquidar_alquiler, name='liquidar_alquiler'),
    path('admin/alquileres/finalizar/<int:id>/', views.finalizar_alquiler, name='finalizar_alquiler'),

    # //////////// GESTIÓN DE RESERVAS DE EVENTOS (LOGÍSTICA) ////////////
    path('admin/reservas/', views.listar_reservas, name='listar_reservas'),
    path('admin/reservas/crear/', views.mostrar_registro_reserva, name='mostrar_registro_reserva'),
    path('admin/reservas/registrar/', views.registrar_reserva, name='registrar_reserva'),
    path('admin/reservas/consultar/<int:id>/', views.mostrar_detalle_reserva, name='mostrar_detalle_reserva'),
    path('admin/reservas/pre-editar/<int:id>/', views.pre_editar_reserva, name='pre_editar_reserva'),
    path('admin/reservas/editar/<int:id>/', views.editar_reserva, name='editar_reserva'),
    
    # //////////// FLUJO DE POST-EVENTO (DAÑOS Y DINERO) ////////////
    path('admin/reservas/estado/<int:id>/<str:nuevo_estado>/', views.cambiar_estado_evento, name='cambiar_estado'),
    path('admin/reservas/evaluar/<int:id>/', views.evaluar_evento_inventario, name='evaluar_evento_inventario'),
    path('admin/reservas/liquidar/<int:id>/', views.liquidar_deposito, name='liquidar_deposito'),

    # //////////// GESTIÓN DE CATÁLOGOS (STAFF) ////////////
    path('admin/catalogos/', views.gestionar_catalogos, name='gestionar_catalogos'),

    path('admin/menus/crear/', views.mostrar_registro_menu, name='mostrar_registro_menu'),
    path('admin/menus/registrar/', views.registrar_menu, name='registrar_menu'),
    path('admin/menus/pre-editar/<int:id>/', views.pre_editar_menu, name='pre_editar_menu'),
    path('admin/menus/actualizar/', views.editar_menu, name='editar_menu'),
    path('admin/menus/eliminar/<int:id>/', views.eliminar_menu, name='eliminar_menu'),
    path('admin/menus/habilitar/<int:id>/', views.habilitar_menu, name='habilitar_menu'),



    path('admin/lugares/crear/', views.mostrar_registro_lugar, name='mostrar_registro_lugar'),
    path('admin/lugares/registrar/', views.registrar_lugar, name='registrar_lugar'),
    path('admin/lugares/pre-editar/<int:id>/', views.pre_editar_lugar, name='pre_editar_lugar'),
    path('admin/lugares/actualizar/', views.editar_lugar, name='editar_lugar'),
    path('admin/lugares/eliminar/<int:id>/', views.eliminar_lugar, name='eliminar_lugar'),
    path('admin/lugares/habilitar/<int:id>/', views.habilitar_lugar, name='habilitar_lugar'),

    path('cambiar-estado/<str:tipo>/<int:id>/', views.cambiar_estado_catalogo, name='cambiar_estado_catalogo'),
]