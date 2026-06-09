# usuarios/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # //////////// NAVEGACIÓN BÁSICA ////////////
    path('', views.home, name='home'),
    path('nosotros/', views.nosotros, name="nosotros"),
    path('dashboard_admin/', views.dashboard_admin, name="dashboard_admin"),
    path('dashboard_bodega/', views.dashboard_bodega, name="dashboard_bodega"),
    path('dashboard_organizador/', views.dashboard_organizador, name="dashboard_organizador"),

    # //////////// AUTENTICACIÓN ////////////
    path('login/', views.iniciar_sesion, name="iniciar_sesion"),
    path('logout/', views.cerrar_sesion, name="logout"),
    path('cambiar-clave/', views.cambiar_clave, name='cambiar_clave'),
    path('registro-cliente/', views.registro_cliente, name="registro"),

    # //////////// PERFIL ////////////
    path('perfil/', views.mi_perfil, name='mi_perfil'),

    # //////////// GESTIÓN DE USUARIOS (STAFF) ////////////
    path('usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('usuarios/crear/', views.mostrar_registro_usuario, name='mostrar_registro_usuario'),
    path('usuarios/registrar/', views.registrar_usuario, name='registrar_usuario'),
    path('usuarios/detalle/<int:id>/', views.mostrar_detalle_usuario, name='mostrar_detalle_usuario'),
    path('usuarios/editar/<int:id>/', views.pre_editar_usuario, name='pre_editar_usuario'),
    path('usuarios/actualizar/', views.editar_usuario, name='editar_usuario'),
    
    # //////////// ESTADOS DE USUARIO ////////////
    path('usuarios/eliminar/<int:id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/habilitar/<int:id>/', views.usuarios_habilitar, name='usuarios_habilitar'),
]