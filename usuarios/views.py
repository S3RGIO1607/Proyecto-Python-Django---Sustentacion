from datetime import date, timedelta
from django.utils import timezone
from django.contrib import messages
import calendar
from django.contrib.auth.hashers import check_password

from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect, render

from .models import Usuario, Rol
from inventario.models import Producto, MovimientoProducto
from operaciones.models import Alquiler, Pago, ReservaEvento, Servicio, Lugar, MenuComida
from django.db.models import Count, Sum


from django.contrib.auth.hashers import make_password
import re # Para validar la complejidad con expresiones regulares

# Create your views here.

#////////////////////    REDIRECCIONES PARA LAS VISTAS DE LA PAGINA PRINCIPAL     ////////////////////

def home(request):
    return render(request, 'index.html') 

def nosotros(request):
    return render(request, 'nosotros.html') 


#////////////////////    PROCESO DEL LOGIN - LOGOUT DE USUARIOS     ////////////////////

def iniciar_sesion(request):
    if request.method == "POST":
        numero_documento = request.POST.get("numero_documento")
        contrasena = request.POST.get("contrasena")

        try:
            # 1. Buscamos al usuario solo por documento
            usuario = Usuario.objects.get(numero_documento=numero_documento)

            # 2. Verificamos si la contraseña coincide (aunque esté encriptada)
            if not check_password(contrasena, usuario.contrasena):
                raise Usuario.DoesNotExist # Forzamos que vaya al error si no coincide

            # 3. Verificamos si está activo
            if usuario.estado != 'A':
                return render(request, "iniciar_sesion.html", {
                    "error": "Este usuario está inactivo. Contacte al administrador."
                })

            # --- Si todo está bien, guardamos la sesión ---
            request.session["usuario_id"] = usuario.id
            request.session["nombre_usuario"] = usuario.nombre
            request.session["rol"] = usuario.rol.id
            request.session["rol_nombre"] = usuario.rol.nombre

            rol_id = usuario.rol.id

            # Redirecciones (se mantienen igual que tu código original)
            if rol_id == 4:   # Cliente
                return redirect("home")
            elif rol_id == 1: # Administrador
                return redirect("dashboard_admin")
            elif rol_id == 2: # Organizador/Staff
                return redirect("dashboard_organizador")
            elif rol_id == 3: # Supervisor Bodega
                return redirect("dashboard_bodega")
            else:
                return redirect("home")

        except Usuario.DoesNotExist:
            # Este error saltará tanto si el documento no existe como si la clave está mal
            return render(request, "iniciar_sesion.html", {
                "error": "Documento o contraseña incorrectos"
            })

    return render(request, "iniciar_sesion.html")

def cerrar_sesion(request):
    request.session.flush()  # elimina toda la sesión
    return redirect("/") 



#////////////////////    PROCESO DE CAMBIO DE CONTRASEÑA     ////////////////////

def cambiar_clave(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    if request.method == "POST":
        clave_actual = request.POST.get("clave_actual")
        nueva_clave = request.POST.get("nueva_clave")
        confirmar_clave = request.POST.get("confirmar_clave")
        
        usuario = Usuario.objects.get(id=request.session["usuario_id"])

        # Validación simple
        if usuario.contrasena != clave_actual: # Si usas hashing, compara con el hash
            messages.error(request, "La contraseña actual no es correcta.")
        elif nueva_clave != confirmar_clave:
            messages.error(request, "Las nuevas contraseñas no coinciden.")
        else:
            usuario.contrasena = nueva_clave
            usuario.save()
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect('mi_perfil')

    return render(request, "cambiar_clave.html")


#////////////////////    REDIRECCION DE USUSUARIO LOGIN (Admin - Sup_Bodega - Organizador)     ////////////////////

def dashboard_admin(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    usuario = Usuario.objects.get(id=request.session["usuario_id"])
    # --- 1. INDICADORES SUPERIORES ---
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0)
    proximos_7_dias = hoy + timedelta(days=7)
    proximas_48_h = hoy + timedelta(hours=48)

    total_pagos_mes = Pago.objects.filter(fecha__gte=inicio_mes).aggregate(Sum('monto'))['monto__sum'] or 0
    eventos_proximos = ReservaEvento.objects.filter(fecha_evento__range=[hoy, proximos_7_dias], estado='Confirmado').count()
    alquileres_proximos = Alquiler.objects.filter(fecha_inicio__range=[hoy, proximas_48_h], estado='Confirmado').count()

    # --- 2. DATOS PARA GRÁFICA (Desempeño Diario del Mes Actual) ---
    hoy = timezone.now()
    # Obtenemos el último día del mes actual
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    
    meses_labels = [] # Ahora serán días: ["1", "2", "3"...]
    data_eventos = []
    data_alquileres = []

    # Iteramos por cada día del mes hasta el día de hoy (o hasta el final del mes)
    for dia in range(1, ultimo_dia + 1):
        meses_labels.append(str(dia))
        
        # Filtros específicos por día
        ev_count = ReservaEvento.objects.filter(
            fecha_evento__day=dia, 
            fecha_evento__month=hoy.month, 
            fecha_evento__year=hoy.year
        ).count()
        
        al_count = Alquiler.objects.filter(
            fecha_inicio__day=dia, 
            fecha_inicio__month=hoy.month, 
            fecha_inicio__year=hoy.year
        ).count()
        
        data_eventos.append(ev_count)
        data_alquileres.append(al_count)

    # --- 3. TOP PRODUCTOS RENTABLES ---
# Usamos 'alquilerproducto' que es el nombre que Django te dio en el error
    top_productos = Producto.objects.annotate(
        total_rentas=Count('alquilerproducto') 
    ).order_by('-total_rentas')[:5]

    # Usamos 'nombre_producto' que es el nombre real de tu campo en el modelo
    prod_labels = [p.nombre_producto for p in top_productos]
    prod_data = [p.total_rentas for p in top_productos]

    # --- 4. ACTIVIDAD RECIENTE ---
    ultimos_movimientos = MovimientoProducto.objects.select_related('producto').order_by('-id')[:5]

    actividades = []
    for mov in ultimos_movimientos:
        # Definir el origen del movimiento
        origen = "Ajuste manual"
        if mov.alquiler:
            origen = f"Alquiler #{mov.alquiler.id}"
        elif mov.reserva:
            origen = f"Reserva #{mov.reserva.id}"

        # ¡IMPORTANTE!: Mueve el append adentro del for
        actividades.append({
            'tipo': 'stock',
            'titulo': f"Mov: {mov.producto.nombre_producto}",
            'subtitulo': f"Origen: {origen}",
            # Usamos getattr por seguridad si el campo 'fecha' no existe aún
            'tiempo': getattr(mov, 'fecha', 'Reciente'), 
            'color': 'vinotinto'
        })

    context = {
        "user": usuario,
        'total_pagos_mes': total_pagos_mes,
        'eventos_proximos': eventos_proximos,
        'alquileres_proximos': alquileres_proximos,
        'meses_labels': meses_labels,
        'data_eventos': data_eventos,
        'data_alquileres': data_alquileres,
        'prod_labels': prod_labels,
        'prod_data': prod_data,
        'actividades': actividades,
    }

    return render(request, 'dashboard_admin.html', context)

def dashboard_bodega(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    usuario = Usuario.objects.get(id=request.session["usuario_id"])
    hoy = timezone.now()

    # --- 1. LÓGICA DE STOCK CRÍTICO ---
    # Traemos productos donde el stock disponible sea menor a 10 (o tu métrica)
    productos_alerta = Producto.objects.filter(stock_disponible__lt=10).order_by('stock_disponible')[:5]
    productos_bajo_stock_count = Producto.objects.filter(stock_disponible__lt=10).count()

    # --- 2. LÓGICA DE RETORNOS (ALQUILERES) ---
    # Alquileres que terminan hoy o están "En Curso" y deben volver
    retornos_pendientes = Alquiler.objects.filter(estado='En Curso').count()

    # --- 3. MOVIMIENTOS RECIENTES ---
    # Corregimos el nombre para que coincida con el HTML
    ultimos_movimientos = MovimientoProducto.objects.select_related('producto').order_by('-id')[:6]

    context = {
        "user": usuario,
        "productos_alerta": productos_alerta,
        "productos_bajo_stock": productos_bajo_stock_count,
        "retornos_hoy": retornos_pendientes,
        "ultimos_movimientos": ultimos_movimientos,
    }

    return render(request, 'dashboard_bodega.html', context)


def dashboard_organizador(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('iniciar_sesion')
    
    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return redirect('iniciar_sesion')

    # 1. Indicadores
    hoy = date.today()
    proximos_7_dias = hoy + timedelta(days=7)
    
    eventos_proximos = ReservaEvento.objects.filter(estado='Confirmado', fecha_evento__gte=hoy).count()
    eventos_evaluacion = ReservaEvento.objects.filter(estado='Finalizado').count()

    # 2. Agenda (Próximos 7 días) con select_related para evitar muchas consultas a DB
    eventos_semana = ReservaEvento.objects.filter(
        fecha_evento__range=[hoy, proximos_7_dias]
    ).select_related('usuario', 'paquete', 'lugar').order_by('fecha_evento')

    # 3. Menú y Lugar TOP
    menu_top = MenuComida.objects.annotate(num_pedidos=Count('reservaevento')).order_by('-num_pedidos').first()
    lugar_mas_reservado = Lugar.objects.annotate(total_reservas=Count('reservaevento')).order_by('-total_reservas').first()

    context = {
        'user': usuario,
        'eventos_proximos': eventos_proximos,
        'eventos_evaluacion': eventos_evaluacion,
        'eventos_semana': eventos_semana,
        'menu_top': menu_top,
        'lugar_mas_reservado': lugar_mas_reservado,
    }
    return render(request, 'dashboard_organizador.html', context)



#////////////////////    GESTION PERFIL USUARIOS     ////////////////////

def mi_perfil(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("iniciar_sesion")

    usuario = get_object_or_404(Usuario, id=usuario_id)

    eventos_asignados = ReservaEvento.objects.filter(organizador_encargado=usuario).select_related('paquete', 'lugar').order_by('-fecha_evento')
    
    base_template = "base.html" if usuario.rol.id == 4 else "base2.html"

    return render(request, "Usuarios/perfil.html", {
        "usuario": usuario,
        "eventos_asignados": eventos_asignados,
        "base_to_extend": base_template  # Pasamos el nombre del archivo
    })





#////////////////////    PROCESO DE GESTION USUARIOS     ////////////////////

def listar_usuarios(request):
    usuarios = Usuario.objects.filter(estado="A")
    usuarios_inactivos = Usuario.objects.filter(estado="I")

    data = {
        'usuarios': usuarios,
        'usuarios_inactivos': usuarios_inactivos
    }

    return render(request, 'Usuarios/index.html', data)

def mostrar_detalle_usuario(request, id):
    roles = Rol.objects.all()
    usuario = get_object_or_404(Usuario, id=id)

    eventos_asignados = ReservaEvento.objects.filter(organizador_encargado=usuario).select_related('paquete').order_by('-fecha_evento')
    
    data = {
        'roles': roles, 
        'usuario': usuario,
        'eventos_asignados': eventos_asignados  # Enviamos los eventos directo al template
    }
    return render(request, 'Usuarios/consultar.html', data)


def mostrar_registro_usuario(request):
    roles=Rol.objects.all()
    data={'roles':roles}
    return render(request,'Usuarios/crear.html',data)

def registrar_usuario(request):
    if request.method == 'POST':
        # 1. Capturamos los datos usando .get() para evitar errores si un campo llega vacío
        numero_documento = request.POST.get('txt_numero_documento')
        nombre = request.POST.get('txt_nombre')
        correo = request.POST.get('txt_correo')
        contrasena = request.POST.get('txt_contrasena')
        direccion = request.POST.get('txt_direccion')
        telefono = request.POST.get('txt_telefono')
        nivel_educativo = request.POST.get('txt_nivel_educativo')
        referencia_personal = request.POST.get('txt_referencia_personal')
        telefono_referencia_personal = request.POST.get('txt_telefono_referencia_personal')
        eps = request.POST.get('txt_eps')
        rol_id = request.POST.get('txt_rol')

        # Traemos los roles por si toca recargar la página por un error
        roles = Rol.objects.all()

        # Contexto base para reenviar los datos digitados si algo falla
        contexto_error = {
            'roles': roles,
            'usuario': {
                'numeroDocumento': numero_documento,
                'nombre': nombre,
                'correo': correo,
                'direccion': direccion,
                'telefono': telefono,
                'nivelEducativo': nivel_educativo,
                'referenciaPersonal': referencia_personal,
                'telefonoReferenciaPersonal': telefono_referencia_personal,
                'eps': eps,
                'rol': {'id': int(rol_id) if rol_id else None}
            }
        }

        # --- VALIDACIONES DE DUPLICADOS EN BASE DE DATOS ---

        # 1. Validar si el correo ya existe
        if Usuario.objects.filter(correo=correo).exists():
            contexto_error['error'] = f'El correo electrónico "{correo}" ya está registrado por otro usuario.'
            return render(request, 'Usuarios/crear.html', contexto_error)

        # 2. Validar si el documento ya existe
        if Usuario.objects.filter(numero_documento=numero_documento).exists():
            contexto_error['error'] = f'El número de documento "{numero_documento}" ya está registrado.'
            return render(request, 'Usuarios/crear.html', contexto_error)


        # --- TUS VALIDACIONES DE SEGURIDAD DE CONTRASEÑA ---
        
        # A. Evitar que la clave sea igual al documento
        if contrasena == numero_documento:
            contexto_error['error'] = "La contraseña no puede ser igual al número de documento."
            return render(request, 'Usuarios/crear.html', contexto_error)

        # B. Forzar longitud mínima (8 caracteres)
        if len(contrasena) < 8:
            contexto_error['error'] = "La contraseña debe tener al menos 8 caracteres."
            return render(request, 'Usuarios/crear.html', contexto_error)

        # C. Validar complejidad (al menos un número, una mayúscula, una minúscula y un carácter especial)
        # Ajustado para acoplarse al 100% con los requisitos visuales que pusimos en el HTML
        if not re.search(r'[a-z]', contrasena) or not re.search(r'[A-Z]', contrasena) or not re.search(r'\d', contrasena) or not re.search(r'[^A-Za-z0-9]', contrasena):
            contexto_error['error'] = "La contraseña no cumple con los requisitos: debe incluir mayúscula, minúscula, número y un símbolo."
            return render(request, 'Usuarios/crear.html', contexto_error)

        # --- FIN DE VALIDACIONES ---

        try:
            rol_obj = Rol.objects.get(id=rol_id)
            
            # Guardamos en la base de datos
            Usuario.objects.create(
                numero_documento = numero_documento,
                nombre = nombre,
                correo = correo,
                contrasena = make_password(contrasena), # Contraseña encriptada de forma segura
                direccion = direccion,
                telefono = telefono,
                nivel_educativo = nivel_educativo,
                referencia_personal = referencia_personal,
                telefono_referencia_personal = telefono_referencia_personal,
                eps = eps,
                rol = rol_obj
            )
            
            messages.success(request, f"Usuario {nombre} registrado exitosamente.")
            return redirect('listar_usuarios')

        except Exception as e:
            contexto_error['error'] = f"Error inesperado al guardar en el sistema: {e}"
            return render(request, 'Usuarios/crear.html', contexto_error)
            
    # Si entran por GET (Carga inicial de la página)
    roles = Rol.objects.all()
    return render(request, 'Usuarios/crear.html', {'roles': roles})

def pre_editar_usuario(request,id):
    Rols=Rol.objects.all()
    usuario=Usuario.objects.get(id=id)
    data={'usuario':usuario, 'roles':Rols}
    return render(request,'Usuarios/editar.html',data)

def editar_usuario(request):
    if request.method=='POST':
        id=request.POST['txt_id']
        numero_documento=request.POST['txt_numero_documento']
        nombre=request.POST['txt_nombre']
        correo=request.POST['txt_correo']
        contrasena=request.POST['txt_contrasena']
        direccion=request.POST['txt_direccion']
        telefono=request.POST['txt_telefono']
        nivel_educativo=request.POST['txt_nivel_educativo']
        referencia_personal=request.POST['txt_referencia_personal']
        telefono_referencia_personal=request.POST['txt_telefono_referencia_personal']
        eps=request.POST['txt_eps']
        estado=request.POST['txt_estado']
        id_rol=request.POST['txt_rol']

        rol=Rol.objects.get(id=id_rol   )
        usuario=Usuario.objects.get(id=id)
        print(usuario)
        print(rol)
        usuario.numero_documento=numero_documento
        usuario.nombre=nombre
        usuario.correo=correo
        usuario.contrasena=contrasena
        usuario.direccion=direccion
        usuario.telefono=telefono
        usuario.nivel_educativo=nivel_educativo
        usuario.referencia_personal=referencia_personal
        usuario.telefono_referencia_personal=telefono_referencia_personal
        usuario.eps=eps
        usuario.estado=estado
        usuario.rol=rol

        usuario.save()   
    return redirect('listar_usuarios')
    
def eliminar_usuario(request, id):
    usuario = Usuario.objects.get(id=id)
    usuario.estado = "I"
    usuario.save()
    return redirect('listar_usuarios')

def usuarios_habilitar(request, id):
    usuario = Usuario.objects.get(id=id)
    usuario.estado = "A"
    usuario.save()
    return redirect('listar_usuarios')







#////////////////////    PROCESO DEL CLIENTE     ////////////////////

def registro_cliente(request):
    if request.method == "POST":
        numero_documento = request.POST.get("numero_documento")
        nombre = request.POST.get("nombre")
        correo = request.POST.get("correo")
        contrasena = request.POST.get("contrasena")
        direccion = request.POST.get("direccion")
        telefono = request.POST.get("telefono")

        # Armamos el diccionario de retorno por si ocurre un fallo en los filtros
        contexto_error = {
            "datos": {
                "numero_documento": numero_documento,
                "nombre": nombre,
                "correo": correo,
                "direccion": direccion,
                "telefono": telefono,
            }
        }

        # --- VALIDACIONES CONTRA LA BASE DE DATOS ---
        if Usuario.objects.filter(numero_documento=numero_documento).exists():
            contexto_error["error"] = f"El número de documento '{numero_documento}' ya se encuentra registrado."
            return render(request, "Cliente/registro.html", contexto_error)

        if Usuario.objects.filter(correo=correo).exists():
            contexto_error["error"] = f"El correo electrónico '{correo}' ya está registrado por otro usuario."
            return render(request, "Cliente/registro.html", contexto_error)

        # --- VALIDACIONES DE COMPLEJIDAD DE CONTRASEÑA ---
        if contrasena == numero_documento:
            contexto_error["error"] = "La contraseña no puede ser idéntica a tu número de documento."
            return render(request, "Cliente/registro.html", contexto_error)

        if len(contrasena) < 8:
            contexto_error["error"] = "La contraseña debe tener un mínimo de 8 caracteres."
            return render(request, "Cliente/registro.html", contexto_error)

        if not re.search(r'[a-z]', contrasena) or not re.search(r'[A-Z]', contrasena) or not re.search(r'\d', contrasena) or not re.search(r'[^A-Za-z0-9]', contrasena):
            contexto_error["error"] = "La contraseña debe incluir por lo menos una letra minúscula, una mayúscula, un número y un símbolo especial."
            return render(request, "Cliente/registro.html", contexto_error)

        # --- COMPLETADO DE REGISTRO EN BD ---
        try:
            # Rol cliente (ID: 4)
            rol_cliente = Rol.objects.get(id=4)

            Usuario.objects.create(
                numero_documento=numero_documento,
                nombre=nombre,
                correo=correo,
                contrasena=make_password(contrasena), # Encriptado seguro para la base de datos
                direccion=direccion,
                telefono=telefono,
                rol=rol_cliente,
                estado='A'
            )

            return redirect("iniciar_sesion")

        except Exception as e:
            contexto_error["error"] = f"Error en la base de datos al crear la cuenta: {e}"
            return render(request, "Cliente/registro.html", contexto_error)

    return render(request, "Cliente/registro.html")