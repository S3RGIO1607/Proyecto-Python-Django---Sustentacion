import os
import re
from xml.dom import ValidationErr
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from pyexpat.errors import messages
from django.contrib import messages
from datetime import datetime
from decimal import Decimal
from datetime import date
from django.db import transaction
from datetime import date, timedelta
from django.db.models import Sum
from django.utils import timezone

from arrons import settings
from .models import ReservaEvento, ReservaServicio, Pago, MenuComida, Lugar, Alquiler, AlquilerProducto, EvaluacionEvento
from usuarios.models import Usuario
from paquetes.models import Paquete, Servicio
from inventario.models import Producto
from .calendar_service import crear_evento
from weasyprint import HTML
from django.http import HttpResponse

# Create your views here.


#////////////////////    GESTION DE ALQUILERES     ////////////////////

def listar_alquileres(request):
    # Verificamos que no sea un cliente el que intenta entrar aquí
    if request.session.get('rol') == 4:
        return redirect('home')

    # Alquileres que requieren atención (Gestión de stock o entrega)
    alquileres_activos = Alquiler.objects.filter(
        estado__in=['Reservado', 'Confirmado', 'En Curso']
    ).order_by('-id')

    # Historial (Ya terminados o cancelados)
    alquileres_historial = Alquiler.objects.filter(
        estado__in=['Devuelto', 'Finalizado', 'Cancelado']
    ).order_by('-id')

    return render(request, 'Alquileres/index.html', {
        'alquileres_activos': alquileres_activos,
        'alquileres_historial': alquileres_historial
    })


def mostrar_detalle_alquiler(request, id):
    if request.session.get('rol') == 4: # Bloquear clientes si es necesario
        return redirect('home')
        
    alquiler = get_object_or_404(Alquiler, id=id)
    # Obtenemos los productos asociados a este alquiler
    productos_alquilados = AlquilerProducto.objects.filter(alquiler=alquiler)
    
    return render(request, 'Alquileres/consultar.html', {
        'alquiler': alquiler,
        'productos_alquilados': productos_alquilados
    })



#////////////////////    GESTION DE LAS RESERVAS     ////////////////////

def listar_reservas(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    # Usamos distinct() para que no se repitan por cada producto evaluado
    todas = ReservaEvento.objects.select_related('usuario', 'paquete', 'lugar').all().order_by('-fecha_evento')
    
    # Historial de los últimos 10 eventos terminados
    eventos_finalizados = ReservaEvento.objects.filter(
        estado="Finalizado"
    ).select_related('usuario', 'paquete').order_by('-fecha_evento')[:10]

    # --- NUEVA CONSULTA ---
    # Filtramos los usuarios que tengan asignado el rol de Organizador.
    # NOTA: Ajusta 'id_rol=3' o 'rol="Organizador"' según cómo manejes los roles en tu base de datos.
    organizadores = Usuario.objects.filter(rol_id=2, estado='A') 

    return render(request, "Reserva/index.html", {
        "reservas_pendientes": todas.filter(estado="Reservado"),
        "reservas_confirmadas": todas.filter(estado__in=["Confirmado", "En Preparacion"]), 
        "eventos_activos": todas.filter(estado="Evento Activo"),
        
        # Filtro de evaluación (Añadido .distinct())
        "por_evaluar": todas.filter(
            estado='Evaluacion', 
            evaluacionevento__isnull=True
        ).distinct(),
        
        # Filtro de liquidación (Añadido .distinct())
        "por_liquidar": todas.filter(
            estado='Evaluacion', 
            evaluacionevento__isnull=False
        ).distinct(),
        
        "finalizados": eventos_finalizados,

        "organizadores_disponibles": organizadores,
    })


def mostrar_registro_reserva(request):
    #Formulario

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    
    paquetes = Paquete.objects.filter(estado='A')
    servicios = Servicio.objects.filter(estado='A')
    usuarios = Usuario.objects.filter(estado='A', rol__id=4)  # Solo clientes

    return render(request, 'Reserva/crear.html', {
        'paquetes': paquetes,
        'servicios': servicios,
        'usuarios': usuarios
    })


def registrar_reserva(request):
    # Traemos solo lo activo
    paquetes = Paquete.objects.filter(estado='A')
    servicios = Servicio.objects.filter(estado='A')

    # Filtramos el contenido interno de cada paquete para el HTML
    for p in paquetes:
        # Esto crea una lista de servicios activos DE ESE paquete
        p.servicios_activos = p.paqueteservicio_set.filter(servicio__estado='A')

    if request.method == "POST":
        usuario_id = request.POST.get("usuario_id")
        paquete_id = request.POST.get("paquete_id")
        fecha_evento = request.POST.get("fecha_evento")

        try:
            usuario = Usuario.objects.get(id=usuario_id)
            paquete = Paquete.objects.get(id=paquete_id, estado='A')
        except:
            messages.error(request, "Usuario o paquete inválido")
            return redirect("crear_reserva_evento")

        reserva = ReservaEvento.objects.create(
            usuario=usuario,
            paquete=paquete,
            fecha_evento=fecha_evento,
            precio_paquete=paquete.precio
        )

        servicios_ids = request.POST.getlist("servicios_ids")
        for sid in servicios_ids:
            try:
                servicio = Servicio.objects.get(id=sid, estado='A')
                cantidad = int(request.POST.get(f"cantidad_servicio_{sid}", 1))
                if cantidad > 0:
                    ReservaServicio.objects.create(
                        reserva=reserva,
                        servicio=servicio,
                        cantidad=cantidad,
                        precio_fijado=servicio.precio_servicio
                    )
            except:
                continue

        reserva.calcular_total()
        messages.success(request, "Reserva creada correctamente")
        return redirect("listar_reservas")

    context = {
        "paquetes": paquetes,
        "servicios": servicios
    }
    return render(request, "Reserva/crear.html", context)



def mostrar_detalle_reserva(request, id):
    reserva = get_object_or_404(ReservaEvento, id=id)
    servicios = reserva.servicios_extra.all()

    context = {
        "reserva": reserva,
        "servicios": servicios
    }

    return render(request, "Reserva/consultar.html", context)


def pre_editar_reserva(request, id):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    
    reserva = get_object_or_404(ReservaEvento, id=id)
    paquetes = Paquete.objects.filter(estado='A')
    servicios = Servicio.objects.filter(estado='A')
    usuarios = Usuario.objects.filter(estado='A', rol__id=4)  # Solo clientes

    context = {
        "reserva": reserva,
        "paquetes": paquetes,
        "servicios": servicios,
        "usuarios": usuarios
    }

    return render(request, "Reserva/editar.html", context)


def editar_reserva(request, id):

    reserva = get_object_or_404(ReservaEvento, id=id)

    paquetes = Paquete.objects.all()
    servicios = Servicio.objects.all()
    usuarios = Usuario.objects.all()

    if request.method == "POST":

        usuario_id = request.POST.get("usuario_id")
        paquete_id = request.POST.get("paquete_id")
        fecha_evento = request.POST.get("fecha_evento")

        usuario = Usuario.objects.get(id=usuario_id)
        paquete = Paquete.objects.get(id=paquete_id)

        # 🔥 ACTUALIZAR RESERVA
        reserva.usuario = usuario
        reserva.paquete = paquete
        reserva.fecha_evento = fecha_evento
        reserva.precio_paquete = paquete.precio
        reserva.save()

        # 🔥 BORRAR SERVICIOS ANTERIORES
        ReservaServicio.objects.filter(reserva=reserva).delete()

        # 🔥 CREAR NUEVOS
        servicios_ids = request.POST.getlist("servicios_ids")

        for sid in servicios_ids:
            servicio = Servicio.objects.get(id=sid)
            cantidad = int(request.POST.get(f"cantidad_servicio_{sid}", 1))

            if cantidad > 0:
                ReservaServicio.objects.create(
                    reserva=reserva,
                    servicio=servicio,
                    cantidad=cantidad,
                    precio_fijado=servicio.precio_servicio
                )

        # 🔥 RECALCULAR
        reserva.calcular_total()

        return redirect("mostrar_detalle_reserva", reserva.id)

    # 🔥 DATOS PARA EL TEMPLATE
    servicios_reserva = reserva.servicios_extra.all()

    servicios_seleccionados = {
        s.servicio.id: s.cantidad for s in servicios_reserva
    }

    for s in servicios:
        if s.id in servicios_seleccionados:
            s.seleccionado = True
            s.cantidad = servicios_seleccionados[s.id]
        else:
            s.seleccionado = False
            s.cantidad = 1

    context = {
        "reserva": reserva,
        "paquetes": paquetes,
        "servicios": servicios,
        "usuarios": usuarios
    }

    return render(request, "Reserva/editar.html", context)



#////////////////////    RESERVAS GENERADAS POR EL CLIENTE     ////////////////////

def mis_reservas(request):
    if not request.session.get("usuario_id"):
        return redirect("iniciar_sesion")

    usuario_id = request.session.get("usuario_id")

    # 1. Obtener Reservas de Eventos (Paquetes)
    reservas = ReservaEvento.objects.filter(
        usuario_id=usuario_id
    ).order_by('-id')

    # 2. Obtener Alquileres de Productos (Carrito)
    alquileres = Alquiler.objects.filter(
        usuario_id=usuario_id
    ).order_by('-id')

    context = {
        "reservas": reservas,
        "alquileres": alquileres,
    }

    return render(request, "Cliente/mis_reservas.html", context)


def crear_reserva_cliente(request, paquete_id):
    if not request.session.get("usuario_id"):
        return redirect("iniciar_sesion")

    usuario_id = request.session.get("usuario_id")
    paquete = get_object_or_404(Paquete, id=paquete_id)
    
    servicios_base_ids = paquete.paqueteservicio_set.values_list('servicio_id', flat=True)
    servicios_disponibles = Servicio.objects.filter(estado='A').exclude(id__in=servicios_base_ids)
    
    menus = MenuComida.objects.filter(estado='A')
    lugares = Lugar.objects.filter(estado='A')

    paquete.servicios_activos = paquete.paqueteservicio_set.filter(servicio__estado='A')
    paquete.productos_activos = paquete.paqueteproducto_set.filter(producto__estado='A')
    
    hoy = date.today().strftime('%Y-%m-%d')

    if request.method == "POST":
        fecha_evento_str = request.POST.get("fecha_evento")
        hora_inicio_str = request.POST.get("hora_inicio")
        asistentes_input = request.POST.get("asistentes")
        menu_id = request.POST.get("menu_id")
        lugar_id = request.POST.get("lugar_id")
        
        # Estructura de persistencia por si ocurre un fallo
        contexto_error = {
            "paquete": paquete, "servicios": servicios_disponibles,
            "menus": menus, "lugares": lugares, "hoy": hoy,
            "datos_enviados": {
                "fecha_evento": fecha_evento_str, "hora_inicio": hora_inicio_str,
                "asistentes": asistentes_input, "menu_id": menu_id, "lugar_id": lugar_id
            }
        }

        # 1. Validaciones de Formato y Tiempos de Fecha/Hora
        try:
            hora_inicio_obj = datetime.strptime(hora_inicio_str, "%H:%M").time()
            fecha_evento_obj = datetime.strptime(fecha_evento_str, "%Y-%m-%d").date()
            
            dt_combinado = datetime.combine(fecha_evento_obj, hora_inicio_obj)
            dt_aware = timezone.make_aware(dt_combinado)
            
            if dt_aware < timezone.now():
                contexto_error["error"] = "No puedes programar eventos para fechas u horas pasadas."
                return render(request, "Cliente/crear_reserva.html", contexto_error)
        except (ValueError, TypeError):
            contexto_error["error"] = "Formato de fecha u hora no válido."
            return render(request, "Cliente/crear_reserva.html", contexto_error)

        # 2. Validación Numérica Rigurosa de Invitados
        try:
            asistentes = int(asistentes_input)
            if asistentes < paquete.capacidad_base:
                contexto_error["error"] = f"La cantidad de invitados no puede ser menor a la capacidad base del paquete ({paquete.capacidad_base} personas)."
                return render(request, "Cliente/crear_reserva.html", contexto_error)
        except (ValueError, TypeError):
            contexto_error["error"] = "El número de asistentes debe ser un dígito numérico válido."
            return render(request, "Cliente/crear_reserva.html", contexto_error)

        # 3. Validación de Locación frente al Aforo de Invitados
        if not lugar_id:
            contexto_error["error"] = "Es obligatorio seleccionar un lugar para la celebración de tu evento."
            return render(request, "Cliente/crear_reserva.html", contexto_error)
            
        lugar_seleccionado = get_object_or_404(Lugar, id=lugar_id)
        if asistentes > lugar_seleccionado.capacidad_maxima:
            contexto_error["error"] = f"El lugar '{lugar_seleccionado.nombre}' no tiene suficiente espacio para albergar a {asistentes} invitados (Máx: {lugar_seleccionado.capacidad_maxima})."
            return render(request, "Cliente/crear_reserva.html", contexto_error)

        # 4. Guardado Transaccional Atómico
        try:
            with transaction.atomic():
                reserva = ReservaEvento(
                    usuario_id=usuario_id,
                    paquete=paquete,
                    fecha_evento=fecha_evento_obj,
                    hora_inicio=hora_inicio_obj,
                    asistentes=asistentes,
                    estado="Reservado",
                    precio_paquete=paquete.precio,
                    lugar_id=lugar_seleccionado.id,
                    menu_comida_id=menu_id if menu_id else None
                )

                # Ejecuta cleans internos y validación estructural de cruce de horarios (las 5 horas)
                reserva.full_clean() 
                reserva.save()
                
                reserva.guardar_configuracion_paquete()

                # Servicios Extra
                servicios_extra_ids = request.POST.getlist("servicios")
                for s_id in servicios_extra_ids:
                    servicio = Servicio.objects.get(id=s_id, estado='A')
                    ReservaServicio.objects.create(
                        reserva=reserva, 
                        servicio=servicio,
                        precio_fijado=servicio.precio_servicio, 
                        cantidad=1
                    )

                reserva.calcular_total()

                try:
                    crear_evento(reserva)
                except Exception as e:
                    print("ERROR GOOGLE CALENDAR CONTROLLER:", e)

            messages.success(request, "¡Tu reserva en Arron Eventos ha sido procesada con éxito!")
            return redirect("mis_reservas")
        
        except ValidationErr as e:
            error_final = e.message_dict.get('_all_', [str(e)])[0] if hasattr(e, 'message_dict') else str(e)
            contexto_error["error"] = error_final
            return render(request, "Cliente/crear_reserva.html", contexto_error)

        except Exception as e:
            error_str = str(e)
            error_final = error_str.replace("{'_all_':", "").replace("[", "").replace("]", "").replace("{", "").replace("}", "").replace("'", "").replace('"', "").strip()
            if error_final.startswith("_all_:"):
                error_final = error_final.replace("_all_:", "").strip()
            contexto_error["error"] = error_final
            return render(request, "Cliente/crear_reserva.html", contexto_error)

    return render(request, "Cliente/crear_reserva.html", {
        "paquete": paquete, "servicios": servicios_disponibles,
        "menus": menus, "lugares": lugares, "hoy": hoy
    })

def detalle_reserva(request, reserva_id):

    if not request.session.get("usuario_id"):
        return redirect("iniciar_sesion")

    usuario_id = request.session.get("usuario_id")

    reserva = get_object_or_404(
        ReservaEvento,
        id=reserva_id,
        usuario_id=usuario_id  # 🔒 seguridad
    )

    servicios = ReservaServicio.objects.filter(reserva=reserva)

    pago = Pago.objects.filter(reserva=reserva).first()

    # 5. Pasar todo al contexto (Agregamos 'pago')
    context = {
        "reserva": reserva,
        "servicios": servicios,
        'pago': pago  # <--- Enviamos el pago directamente
    }

    return render(request, "Cliente/detalle_reserva.html", context)


def cancelar_reserva_cliente(request, reserva_id):
    # Buscamos la reserva asegurándonos que sea del usuario actual
    reserva = get_object_or_404(ReservaEvento, id=reserva_id, usuario_id=request.session.get("usuario_id"))
    
    if reserva.estado == 'Reservado':
        reserva.estado = 'Cancelado'
        reserva.save()
        messages.success(request, f"La reserva #{reserva.id} ha sido cancelada exitosamente.")
    else:
        messages.error(request, "Esta reserva no puede ser cancelada en su estado actual.")
        
    return redirect('detalle_reserva', reserva_id=reserva.id)


def registrar_pago_cliente(request, tipo, id_objeto):
    if request.method == "POST":
        monto = request.POST.get('monto')
        metodo = request.POST.get('metodo')  # 'Transferencia', 'Tarjeta' o 'Efectivo'
        
        try:
            with transaction.atomic():
                # 1. Instanciamos el objeto con los datos comunes obligatorios
                nuevo_pago = Pago(
                    usuario_id=request.session['usuario_id'],
                    monto=monto,
                    metodo_pago=metodo,
                    tipo='Final'  # Modificado para alinearse con tus TIPO_PAGO_CHOICES ('Final')
                )
                
                # 2. Captura y asignación condicional según el flujo de la pasarela
                if metodo == 'Transferencia':
                    nuevo_pago.transferencia_banco = request.POST.get('transferencia_banco')
                    nuevo_pago.transferencia_tipo = request.POST.get('transferencia_tipo')
                    nuevo_pago.transferencia_numero = request.POST.get('transferencia_numero')
                    
                elif metodo == 'Tarjeta':
                    nuevo_pago.tarjeta_tipo = request.POST.get('tarjeta_tipo')
                    # Convertimos el nombre a mayúsculas para estandarizar registros bancarios
                    titular_crudo = request.POST.get('tarjeta_titular', '')
                    nuevo_pago.tarjeta_titular = titular_crudo.strip().upper()
                
                # El método 'Efectivo' no requiere recolectar campos extra del POST, 
                # por ende, los campos adicionales se guardarán automáticamente como NULL en la BD.

                # 3. Asociar el pago al contenedor correspondiente (Alquiler o Reserva)
                if tipo == 'alquiler':
                    nuevo_pago.alquiler_id = id_objeto
                    nuevo_pago.save()
                    # Aquí puedes reincorporar tus rutinas como confirmar_alquiler() si aplica
                    
                elif tipo == 'reserva':
                    reserva = get_object_or_404(ReservaEvento, id=id_objeto)
                    nuevo_pago.reserva_id = id_objeto
                    nuevo_pago.save()
                    
                    # Ejecución del método del modelo para actualizar inventarios y despacho
                    reserva.confirmar_y_despachar()
                
            messages.success(request, "¡Pago registrado! El inventario de tu evento ha sido bloqueado con éxito.")
            
        except Exception as e:
            messages.error(request, f"Error al procesar el pago en el sistema: {e}")
            
    return redirect('mis_reservas')



#////////////////////    GESTION DE LOS ESTADOS DE LOS EVENTOS     ////////////////////

def cambiar_estado_evento(request, id, nuevo_estado):
    reserva = get_object_or_404(ReservaEvento, id=id)
    
    # Lista de estados permitidos por seguridad
    estados_validos = ['Confirmado', 'Evento Activo', 'Evaluacion', 'Finalizado']
    
    if nuevo_estado in estados_validos:
        # --- NUEVA LÓGICA PARA ASIGNAR EL ORGANIZADOR ---
        if nuevo_estado == 'Evento Activo' and request.method == 'POST':
            organizador_id = request.POST.get('txt_organizador')
            if organizador_id:
                try:
                    # Buscamos el organizador en la base de datos
                    organizador = Usuario.objects.get(id=organizador_id)
                    # Lo asignamos al campo correspondiente de la reserva
                    reserva.organizador_encargado = organizador
                except Usuario.DoesNotExist:
                    # Si por alguna razón el ID no existe, continúa sin romper el flujo
                    pass

        # Actualizamos el estado de la reserva
        reserva.estado = nuevo_estado
        reserva.save()
        
    # Redirigimos de vuelta al panel de logística
    return redirect('listar_reservas')



#////////////////////    EVALUACIÓN DE DAÑOS Y LIQUIDACIÓN DE DEPÓSITOS     ////////////////////

def evaluar_evento_inventario(request, id):
    reserva = get_object_or_404(ReservaEvento, id=id)
    
    if reserva.estado not in ['Evento Activo', 'Evaluacion']:
        messages.warning(request, "Este evento no está en etapa de evaluación.")
        return redirect('mostrar_detalle_reserva', reserva.id)

    productos_reserva = reserva.productos.all()

    if request.method == "POST":
        # Bandera para validar que todo esté correcto antes de guardar en la BD
        error_encontrado = False
        
        # Primero validamos todos los datos enviados en un ciclo limpio
        for rp in productos_reserva:
            raw_danados = request.POST.get(f'danados_{rp.id}', '0')
            observacion = request.POST.get(f'obs_{rp.id}', "").strip()
            
            try:
                cantidad_danada = int(raw_danados)
            except ValueError:
                messages.error(request, f"La cantidad enviada para {rp.producto.nombre_producto} no es un número válido.")
                error_encontrado = True
                break

            if cantidad_danada < 0:
                messages.error(request, f"No se admiten números negativos para {rp.producto.nombre_producto}.")
                error_encontrado = True
                break
                
            if cantidad_danada > rp.cantidad:
                messages.error(request, f"Los daños de {rp.producto.nombre_producto} ({cantidad_danada}) exceden lo entregado ({rp.cantidad}).")
                error_encontrado = True
                break

            if cantidad_danada > 0 and not observacion:
                messages.error(request, f"Debes añadir una observación explicando el daño de: {rp.producto.nombre_producto}.")
                error_encontrado = True
                break

        # Si hubo algún error en los datos, volvemos a renderizar la página sin guardar nada
        if error_encontrado:
            return render(request, 'Reserva/evaluar_evento.html', {
                'reserva': reserva,
                'productos_reserva': productos_reserva
            })

        # Si todo es totalmente correcto, procedemos a guardar con seguridad
        for rp in productos_reserva:
            cantidad_danada = int(request.POST.get(f'danados_{rp.id}', 0))
            observacion = request.POST.get(f'obs_{rp.id}', "").strip()
            
            # Multiplicador del costo de reposición (Ej: precio_alquiler * 6)
            costo_calculado = Decimal(cantidad_danada) * (rp.producto.precio_alquiler * Decimal('6'))
            
            EvaluacionEvento.objects.update_or_create(
                reserva=reserva,
                producto=rp.producto,
                defaults={
                    'cantidad_danada': cantidad_danada,
                    'observacion': observacion,
                    'costo_dano': costo_calculado.quantize(Decimal('0.01'))
                }
            )
        
        reserva.estado = 'Evaluacion'
        reserva.save()
        
        messages.success(request, "Evaluación de daños guardada de forma segura. Ahora puedes finalizar el evento.")
        return redirect('mostrar_detalle_reserva', reserva.id)

    return render(request, 'Reserva/evaluar_evento.html', {
        'reserva': reserva,
        'productos_reserva': productos_reserva
    })


def liquidar_deposito(request, id):  # Este es el paso final después de evaluar los daños  EVENTOOOOO
    reserva = get_object_or_404(ReservaEvento, id=id)
    
    # 1. Sumamos todos los costos de daños registrados para esta reserva
    evaluaciones = EvaluacionEvento.objects.filter(reserva=reserva)
    total_danos = evaluaciones.aggregate(Sum('costo_dano'))['costo_dano__sum'] or 0
    
    # 2. Calculamos el saldo a devolver
    saldo_a_devolver = reserva.deposito_garantia - total_danos

    if request.method == "POST":
        # Al confirmar, ejecutamos la lógica de retorno de stock que ya tienes
        reserva.finalizar_y_retornar_stock()
        
        # Actualizamos el estado del depósito
        if total_danos > 0:
            reserva.estado_deposito = 'Usado' # Se usó parte o todo
        else:
            reserva.estado_deposito = 'Devuelto'
            
        reserva.save()
        messages.success(request, f"Liquidación completada. Saldo devuelto: ${saldo_a_devolver}")
        return redirect('mostrar_detalle_reserva', reserva.id)

    return render(request, 'Reserva/liquidar_deposito.html', {
        'reserva': reserva,
        'total_danos': total_danos,
        'saldo_a_devolver': saldo_a_devolver,
        'evaluaciones': evaluaciones
    })



#////////////////////    CREACION ALQUILER CLIENTE     ////////////////////

def calcular_fecha_limite(fecha, dias):
    return fecha + timedelta(days=dias)

def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    subtotal_productos = Decimal('0.00')
    
    for item in carrito.values():
        subtotal_productos += Decimal(str(item['precio'])) * item['cantidad']
    
    # --- LOGICA DE PERSISTENCIA DE FECHA Y TRANSPORTE ---
    if request.method == 'POST':
        # Guardamos el estado del transporte seleccionado
        requiere_transporte = request.POST.get('requiere_transporte') == 'si'
        request.session['transporte_temp'] = requiere_transporte 
        
        # Guardamos la fecha si ya la había seleccionado antes del cambio de transporte
        fecha_alquiler_input = request.POST.get('fecha_alquiler', '').strip()
        if fecha_alquiler_input:
            request.session['fecha_alquiler_temp'] = fecha_alquiler_input
    else:
        # Si entra por GET, recuperamos lo que haya en la sesión o seteamos valores por defecto
        requiere_transporte = request.session.get('transporte_temp', False)

    # Obtenemos la fecha temporal guardada en la sesión para inyectarla al input de Flatpickr
    fecha_alquiler_guardada = request.session.get('fecha_alquiler_temp', '')

    costo_envio = Decimal('50000.00') if requiere_transporte else Decimal('0.00')
    valor_danos = (subtotal_productos * Decimal('0.30')).quantize(Decimal('0.01'))
    total_final = subtotal_productos + valor_danos + costo_envio

    context = {
        'carrito': carrito,
        'subtotal': subtotal_productos,
        'valor_danos': valor_danos,
        'valor_transporte_base': Decimal('50000.00'),
        'costo_envio': costo_envio, 
        'total_final': total_final,
        'requiere_transporte': requiere_transporte,
        'fecha_alquiler_guardada': fecha_alquiler_guardada, # Se renderiza en el input text
    }
    return render(request, 'carrito.html', context)


def agregar_al_carrito(request):
    if request.method == "POST":
        producto_id = request.POST.get('idProducto')
        cantidad_nueva = int(request.POST.get('cantidad', 1))
        
        producto = get_object_or_404(Producto, id=producto_id)
        carrito = request.session.get('carrito', {})
        id_str = str(producto_id)

        # 1. VALIDACIÓN: ¿Lo que intenta agregar de golpe supera el stock?
        if cantidad_nueva > producto.stock_disponible:
            messages.warning(request, f"No puedes agregar {cantidad_nueva} unidades. Solo hay {producto.stock_disponible} disponibles de {producto.nombre_producto}.")
            return redirect('productos_catalogo')

        # 2. VALIDACIÓN ACUMULATIVA: ¿Lo que ya tiene + lo nuevo supera el stock?
        cantidad_previa = carrito.get(id_str, {}).get('cantidad', 0)
        total_acumulado = cantidad_previa + cantidad_nueva

        if total_acumulado > producto.stock_disponible:
            messages.warning(request, f"Ya tienes {cantidad_previa} en el carrito. No puedes sumar {cantidad_nueva} más porque el stock total es de {producto.stock_disponible}.")
            return redirect('productos_catalogo')

        # 3. PROCESO DE AGREGADO (Si pasó las validaciones)
        if id_str in carrito:
            carrito[id_str]['cantidad'] = total_acumulado
        else:
            carrito[id_str] = {
                'id': producto.id,
                'nombre': producto.nombre_producto,
                'precio': str(producto.precio_alquiler),
                'imagen': producto.imagen.url if producto.imagen else '/static/imagenes/placeholder.jpg',
                'cantidad': cantidad_nueva
            }
        
        # Guardar en sesión
        request.session['carrito'] = carrito
        request.session.modified = True
        messages.success(request, f"¡{producto.nombre_producto} añadido correctamente!")
        
    return redirect('productos_catalogo')


def actualizar_carrito(request, producto_id):
    if request.method == "POST":
        # 1. Obtener el carrito de la sesión
        carrito = request.session.get('carrito', {})
        producto_id_str = str(producto_id)

        if producto_id_str in carrito:
            # 2. Consultar el producto en la DB para validar stock real
            producto = get_object_or_404(Producto, id=producto_id)
            accion = request.POST.get('accion') # Viene del atributo 'value' del botón
            cantidad_actual = carrito[producto_id_str]['cantidad']

            if accion == "sumar":
                # Validar que no exceda el stock_disponible de tu SQL
                if cantidad_actual < producto.stock_disponible:
                    carrito[producto_id_str]['cantidad'] += 1
                else:
                    messages.warning(request, f"Solo hay {producto.stock_disponible} unidades disponibles.")
            
            elif accion == "restar":
                # No permitir menos de 1
                if cantidad_actual > 1:
                    carrito[producto_id_str]['cantidad'] -= 1
                else:
                    # Opcional: Si es 1 y resta, puedes elegir eliminarlo o dejarlo en 1
                    pass

            # 3. Guardar cambios en la sesión
            request.session['carrito'] = carrito
            request.session.modified = True

    # 4. Redirigir siempre al carrito para refrescar los totales
    return redirect('ver_carrito')


def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    if str(producto_id) in carrito:
        del carrito[str(producto_id)]
        request.session['carrito'] = carrito
        request.session.modified = True
    return redirect('ver_carrito')


def confirmar_alquiler_carrito(request):
    if "usuario_id" not in request.session:
        messages.error(request, "Debes iniciar sesión para alquilar.")
        return redirect('iniciar_sesion')

    carrito = request.session.get('carrito', {})
    if not carrito:
        return redirect('productos_catalogo')

    # Capturar la opción de transporte desde el formulario
    # Asumiendo que el checkbox en el HTML tiene name="incluye_transporte"
    quiere_transporte = request.POST.get('requiere_transporte') == 'si'
    costo_envio = Decimal('50000.00') if quiere_transporte else Decimal('0.00')

    try:
        fecha_inicio_str = request.POST.get('fecha_alquiler')

        if not fecha_inicio_str:
            messages.error(request, "Debes seleccionar una fecha.")
            return redirect('ver_carrito')

        fecha_inicio = datetime.strptime(
            fecha_inicio_str,
            "%d/%m/%Y"
        ).date()

        fecha_limite = calcular_fecha_limite(fecha_inicio, 3)





        with transaction.atomic():
            # 1. Calcular totales del carrito
            subtotal_productos = Decimal('0.00')
            for item in carrito.values():
                precio = Decimal(str(item['precio']))
                subtotal_productos += precio * item['cantidad']

            # 2. Calcular Garantía (30%)
            valor_garantia = (subtotal_productos * Decimal('0.30')).quantize(Decimal('0.01'))
            
            # 3. SUMA TOTAL INCLUYENDO TRANSPORTE
            total_con_todo = subtotal_productos + valor_garantia + costo_envio

            # 4. Crear el Alquiler con los nuevos campos
            nuevo_alquiler = Alquiler.objects.create(
                usuario_id=request.session['usuario_id'],
                fecha_inicio=fecha_inicio,
                fecha_limite=fecha_limite,
                #Alerta con la fecha limite 
                estado='Reservado',
                valor_alquiler=subtotal_productos,
                deposito_garantia=valor_garantia, 
                valor_danos=Decimal('0.00'),
                # Campos de transporte (Asegúrate de haber corrido las migraciones)
                incluye_transporte=quiere_transporte,
                costo_transporte=costo_envio,
                total_final=total_con_todo 
            )

            # 5. Registrar productos y Validar Stock
            for p_id, item in carrito.items():
                prod = Producto.objects.select_for_update().get(id=p_id)
                
                if prod.stock_disponible < item['cantidad']:
                    raise Exception(f"Stock insuficiente de {prod.nombre_producto}")

                # Registrar relación de productos
                AlquilerProducto.objects.create(
                    alquiler=nuevo_alquiler,
                    producto=prod,
                    cantidad_contratada=item['cantidad'],
                    precio_alquiler_fijado=Decimal(str(item['precio']))
                )

           # 6. Limpiar carrito y temporales de control
            request.session['carrito'] = {}
            if 'transporte_temp' in request.session:
                del request.session['transporte_temp']
            if 'fecha_alquiler_temp' in request.session:
                del request.session['fecha_alquiler_temp']
                
            request.session.modified = True
            
            return redirect('detalle_alquiler', id=nuevo_alquiler.id)

    except Exception as e:
        messages.error(request, f"Error al procesar: {str(e)}")
        return redirect('ver_carrito')
    


#////////////////////    VISUALIZACION DETALLES ALQUILERES CREADOS POR EL CLIENTE     ////////////////////

def detalle_alquiler(request, id):
    # 1. Seguridad: Verificar que el usuario esté logueado
    if "usuario_id" not in request.session:
        return redirect('iniciar_sesion')

    # 2. Obtener el alquiler
    alquiler = get_object_or_404(
        Alquiler, 
        id=id, 
        usuario_id=request.session['usuario_id']
    )

    # 3. Obtener todos los productos asociados
    productos_detalle = AlquilerProducto.objects.filter(
        alquiler=alquiler
    ).select_related('producto')

    # 4. NUEVO: Buscar el pago asociado a este alquiler
    # (Asegúrate de que tu modelo de Pago se llame 'Pago' y que el campo se llame 'alquiler')
    pago = Pago.objects.filter(alquiler=alquiler).first()

    # 5. Pasar todo al contexto (Agregamos 'pago')
    context = {
        'alquiler': alquiler,
        'productos': productos_detalle,
        'pago': pago  # <--- Enviamos el pago directamente
    }

    return render(request, 'Cliente/detalle_alquiler.html', context)



#////////////////////    DESPACHE DE LOS PRODUCTOS REGISTRADOS EN EL ALQUILER     ////////////////////

@transaction.atomic
def despachar_alquiler(request, id):
    # Solo personal de bodega o admin debería poder hacer esto
    alquiler = get_object_or_404(Alquiler, id=id)
    
    if alquiler.estado == 'Confirmado' or alquiler.estado == 'Reservado':
        alquiler.estado = 'En Curso'
        alquiler.save()
        messages.success(request, f"Alquiler #{alquiler.id} ha sido despachado. ¡Los productos ya están en camino!")
    else:
        messages.error(request, "Este alquiler no se puede despachar en su estado actual.")
        
    return redirect('mostrar_detalle_alquiler', id=alquiler.id)



#////////////////////    CREACION DE RETORNOS DE PRODUCTOS DE LOS ALQUILERES     ////////////////////
#Aca dependiendo de la fecha en la que el cliente devuelva se actuALIZA La fecaha del alquiler 
@transaction.atomic
def registrar_retorno(request, id):
    alquiler = get_object_or_404(Alquiler, id=id)
    productos_alquilados = AlquilerProducto.objects.filter(alquiler=alquiler)

    if request.method == "POST":
        try:
            with transaction.atomic():
                total_danos_acumulado = Decimal('0.00')
                from .models import MovimientoProducto
                
                for item in productos_alquilados:
                    bueno = request.POST.get(f'bueno_{item.id}', 0)
                    malo = request.POST.get(f'malo_{item.id}', 0)
                    
                    cant_buena = int(bueno)
                    cant_mala = int(malo)

                    # VALIDACIÓN: La suma debe ser igual a lo contratado
                    if (cant_buena + cant_mala) != item.cantidad_contratada:
                        raise ValueError(f"La suma para {item.producto.nombre_producto} no coincide con lo contratado.")
                    
                    # 1. ACTUALIZAR DETALLE DE PRODUCTOS EN EL ALQUILER
                    item.cantidad_retornada_ok = cant_buena
                    item.cantidad_danada = cant_mala
                    
                    # Cálculo de daños (80% del valor de compra)
                    precio_compra = Decimal(str(item.producto.precio_compra or 0))
                    danos_item = (Decimal(cant_mala) * precio_compra * Decimal('0.80')).quantize(Decimal('0.01'))  
                    
                    item.subtotal_danos = danos_item
                    item.observacion_dano = f"Retorno registrado - Alquiler #{alquiler.id}"
                    item.save()
                    
                    total_danos_acumulado += danos_item

                    # 2. AJUSTE DE INVENTARIO (TOTAL Y DISPONIBLE)
                    producto = item.producto
                    
                    # CASO A: Productos que regresaron bien
                    if cant_buena > 0:
                        # Vuelven al stock disponible para ser alquilados de nuevo
                        producto.stock_disponible += cant_buena
                        
                        # Registrar Movimiento Formal de Entrada vinculado al Alquiler
                        MovimientoProducto.objects.create(
                            producto=producto,
                            alquiler=alquiler,
                            tipo='ENTRADA',
                            cantidad=cant_buena,
                            observacion=f"RETORNO OK - Alquiler #{alquiler.id}"
                        )

                    # CASO B: Productos DAÑADOS (Baja del sistema)
                    if cant_mala > 0:
                        # RESTAMOS DEL STOCK TOTAL (Ya no forman parte del patrimonio)
                        # No se suman al disponible, por lo que el disponible queda reducido permanentemente
                        producto.stock_total -= cant_mala
                        
                        # Registrar Movimiento de Salida por Daño para auditoría
                        MovimientoProducto.objects.create(
                            producto=producto,
                            alquiler=alquiler,
                            tipo='SALIDA',
                            cantidad=cant_mala,
                            observacion=f"BAJA POR DAÑO - Alquiler #{alquiler.id}"
                        )
                    
                    # Guardar cambios finales en el producto
                    producto.save()

                # 3. LÓGICA FINANCIERA FINAL
                alquiler.valor_danos = total_danos_acumulado
                alquiler.total_final = alquiler.valor_alquiler + total_danos_acumulado
                
                saldo_reembolso = alquiler.deposito_garantia - total_danos_acumulado
                if saldo_reembolso < 0:
                    alquiler.observaciones_bodega = f"DAÑOS SUPERAN DEPÓSITO. Cobrar extra: ${abs(saldo_reembolso)}"
                else:
                    alquiler.observaciones_bodega = f"Retorno exitoso. Reembolsar: ${saldo_reembolso}"

                alquiler.fecha_devolucion = timezone.localtime().date()
                alquiler.estado = 'Devuelto'
                alquiler.save()

                messages.success(request, f"Inventario y Daños procesados correctamente. {alquiler.observaciones_bodega}")
                return redirect('mostrar_detalle_alquiler', id=alquiler.id)

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
            
    return render(request, 'Alquileres/registrar_retorno.html', {
        'alquiler': alquiler, 
        'productos_alquilados': productos_alquilados
    })



#////////////////////    CREACION LA LIQUIDACION EN CUANTO AL DEPOSITO RELACIONAD CON EL ALQUILER     ////////////////////

def liquidar_alquiler(request, id):
    alquiler = get_object_or_404(Alquiler, id=id)
    detalles_danos = AlquilerProducto.objects.filter(
        alquiler=alquiler,
        cantidad_danada__gt=0
    )

    saldo = (
        alquiler.deposito_garantia
        - alquiler.valor_danos
        - alquiler.valor_mora
    )

    return render(request, 'Alquileres/liquidar_deposito.html', {
        'alquiler': alquiler,
        'detalles_danos': detalles_danos,
        'saldo_reembolso': saldo,
        'saldo_abs': abs(saldo)
    })



#////////////////////    FINALIZACION DE ALQUILERES     ////////////////////

@transaction.atomic
def finalizar_alquiler(request, id):
    if request.method == "POST":
        alquiler = get_object_or_404(Alquiler, id=id)
        
        # Cambiamos el estado a Finalizado
        alquiler.estado = 'Finalizado'
        alquiler.save()
        
        messages.success(request, f"El alquiler #{alquiler.id} ha sido liquidado y cerrado correctamente.")
        return redirect('listar_alquileres') # O a la vista de historial
    
    return redirect('listar_alquileres')


#////////////////////    COMPROBANTE ALQUILERES / EVENTOS     ////////////////////

def descargar_comprobante_pdf(request, tipo, obj_id):
    """
    tipo: puede ser 'alquiler' o 'reserva'
    obj_id: el ID del registro
    """
    detalles_normalizados = []
    
    if tipo == 'alquiler':
        obj = get_object_or_404(Alquiler, id=obj_id)
        titulo = "COMPROBANTE DE ALQUILER"
        fecha_principal = obj.fecha_inicio
        # Normalizamos los productos de Alquiler
        for item in obj.alquilerproducto_set.all():
            detalles_normalizados.append({
                'nombre': item.producto.nombre_producto,
                'cantidad': item.cantidad_contratada,
                'precio_unit': item.precio_alquiler_fijado,
                'subtotal': item.cantidad_contratada * item.precio_alquiler_fijado,
                'proveedor_nombre': None,   # Los productos no llevan especialista
                'proveedor_telefono': None  # Los productos no llevan especialista
            })
        total = obj.valor_alquiler
        
    else:  # tipo == 'reserva'
        obj = get_object_or_404(ReservaEvento, id=obj_id)
        titulo = "COMPROBANTE DE EVENTO"
        fecha_principal = obj.fecha_evento
        # 1. Normalizamos los productos del Paquete
        for item in obj.productos.all():
            detalles_normalizados.append({
                'nombre': item.producto.nombre_producto,
                'cantidad': item.cantidad,
                'precio_unit': item.precio_unitario_fijado,
                'subtotal': item.subtotal(),
                'proveedor_nombre': None,   # Los productos del paquete no llevan especialista
                'proveedor_telefono': None  # Los productos del paquete no llevan especialista
            })
        # 2. Añadimos servicios extra si existen (AQUÍ AGREGAMOS LA INFO FALTA)
        for serv in obj.servicios_extra.all():
            # Verificamos de forma segura si el servicio tiene un proveedor asignado
            proveedor = serv.servicio.proveedor if hasattr(serv.servicio, 'proveedor') else None
            
            detalles_normalizados.append({
                'nombre': f"Servicio: {serv.servicio.nombre_servicio}",
                'cantidad': serv.cantidad,
                'precio_unit': serv.precio_fijado,
                'subtotal': serv.subtotal(),
                
                # Extraemos la información del proveedor si existe en tu base de datos
                'proveedor_nombre': proveedor.nombre if proveedor else None,
                'proveedor_telefono': proveedor.telefono if proveedor else None
            })
        total = obj.total

    context = {
        'obj': obj,
        'titulo': titulo,
        'fecha_principal': fecha_principal,
        'detalles': detalles_normalizados,
        'total': total,
        'logo_path': os.path.join(settings.BASE_DIR, 'static', 'imagenes', 'logo2.png'),
    }

    html_string = render_to_string('Cliente/pdf_comprobante.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Comprobante_Arron_{obj_id}.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    
    return response


def gestionar_catalogos(request):
    # Traemos todos los datos de tus modelos existentes
    servicios = Servicio.objects.all()
    for s in servicios:
        s.utilidad = (s.precio_servicio or 0) - (s.costo_proveedor or 0)
    context = {
        'servicios': servicios,
        'menus': MenuComida.objects.all(),
        'lugares': Lugar.objects.all(),
    }
    return render(request, 'listar_todo.html', context)


#////////////////////    GESTION DE LOS MENUS     ////////////////////

def mostrar_registro_menu(request):
    #Formulario

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    return render(request, 'Menu/crear.html')

def registrar_menu(request):
    if request.method == "POST":
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        precio_raw = request.POST.get('txt_precio_por_persona', '').strip()

        # Caché de datos para no limpiar los campos en caso de error
        valores_previos = {
            'nombre': nombre,
            'descripcion': descripcion,
            'precio_por_persona': precio_raw
        }

        # 1. VALIDACIÓN: Nombre (Solo letras y espacios, largo de 2 a 50)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre):
            messages.error(request, "El nombre del menú debe contener únicamente letras y tener entre 2 y 50 caracteres.")
            return render(request, 'Menu/crear.html', {'valores_previos': valores_previos})

        # 2. VALIDACIÓN: Descripción (Longitud de 20 a 250 caracteres)
        if len(descripcion) < 20 or len(descripcion) > 250:
            messages.error(request, "La descripción del menú debe tener entre 20 y 250 caracteres.")
            return render(request, 'Menu/crear.html', {'valores_previos': valores_previos})

        # 3. VALIDACIÓN: Precio (Número entero no negativo)
        try:
            precio_por_persona = int(precio_raw)
            if precio_por_persona < 0:
                raise ValueError
        except ValueError:
            messages.error(request, "El precio por persona debe ser un número entero válido sin decimales ni signos negativos.")
            return render(request, 'Menu/crear.html', {'valores_previos': valores_previos})

        # Registro exitoso tras superar todas las defensas
        MenuComida.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            precio_por_persona=precio_por_persona,
            estado='A'
        )

        messages.success(request, "Nueva propuesta gastronómica registrada exitosamente.")
        return redirect('gestionar_catalogos')

    return render(request, 'Menu/crear.html')

def pre_editar_menu(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    menu = MenuComida.objects.get(id=id)
    return render(request, 'Menu/editar.html', {
        'menu': menu
    })

def editar_menu(request):
    if request.method == "POST":
        id_menu = request.POST.get('txt_id')
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        precio_raw = request.POST.get('txt_precio_por_persona', '').strip()
        estado = request.POST.get('txt_estado')

        # Controlar la existencia del menú en la base de datos
        try:
            menu = MenuComida.objects.get(id=id_menu)
        except MenuComida.DoesNotExist:
            messages.error(request, "El menú que intenta editar no se encuentra en el sistema.")
            return redirect('gestionar_catalogos')

        # Cargamos los datos ingresados al objeto de forma temporal (sin guardar)
        menu.nombre = nombre
        menu.descripcion = descripcion
        menu.precio_por_persona = precio_raw  # Mantiene la string en caso de re-renderizar
        menu.estado = estado

        # 1. VALIDACIÓN: Nombre alfabético (2 a 50 letras y espacios)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre):
            messages.error(request, "Error de actualización: El nombre debe contener solo letras y cumplir con una extensión de 2 a 50 caracteres.")
            return render(request, 'Menu/editar.html', {'menu': menu})

        # 2. VALIDACIÓN: Composición del Menú (20 a 250 caracteres)
        if len(descripcion) < 20 or len(descripcion) > 250:
            messages.error(request, "Error de actualización: La composición de platos debe poseer de 20 a 250 caracteres.")
            return render(request, 'Menu/editar.html', {'menu': menu})

        # 3. VALIDACIÓN: Tarifa por Persona (Entero válido y positivo)
        try:
            precio_valido = int(precio_raw)
            if precio_valido < 0:
                raise ValueError
            menu.precio_por_persona = precio_valido  # Seteamos el número entero limpio
        except ValueError:
            messages.error(request, "Error de actualización: La tarifa debe ser un número entero válido sin decimales.")
            return render(request, 'Menu/editar.html', {'menu': menu})

        # Guardado definitivo tras pasar los filtros de seguridad
        menu.save()
        messages.success(request, f"Menú '{nombre}' actualizado correctamente.")
        
    return redirect('gestionar_catalogos')


def eliminar_menu(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    menu = MenuComida.objects.get(id=id)
    menu.estado = "I"
    menu.save()
    return redirect('gestionar_catalogos')

def habilitar_menu(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    menu = MenuComida.objects.get(id=id)
    menu.estado = "A"
    menu.save()
    return redirect('gestionar_catalogos')


#////////////////////    GESTION DE LOS LUGARES     ////////////////////

def mostrar_registro_lugar(request):
    #Formulario

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    return render(request, 'Lugar/crear.html')

def registrar_lugar(request):
    if request.method == "POST":
        nombre = request.POST.get('txt_nombre', '').strip()
        direccion = request.POST.get('txt_direccion', '').strip()
        capacidad_raw = request.POST.get('txt_capacidad_maxima', '').strip()
        precio_raw = request.POST.get('txt_precio_renta', '').strip()
        imagen = request.FILES.get('txt_imagen')

        # Cache temporal de strings por si ocurre un error
        valores_previos = {
            'nombre': nombre,
            'direccion': direccion,
            'capacidad_maxima': capacidad_raw,
            'precio_renta': precio_raw
        }

        # 1. VALIDACIÓN: Nombre de la sede (Alfanumérico de 3 a 60 caracteres)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ0-9\s]{3,60}$', nombre):
            messages.error(request, "El nombre de la sede debe ser alfanumérico y contener entre 3 y 60 caracteres.")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})

        # 2. VALIDACIÓN: Imagen obligatoria y formato válido
        if not imagen:
            messages.error(request, "Es obligatorio subir una fotografía representativa para la locación.")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})
        
        extensiones_validas = ['jpg', 'jpeg', 'png', 'webp']
        ext = imagen.name.split('.')[-1].lower()
        if ext not in extensiones_validas:
            messages.error(request, "Formato de imagen inválido. Solo se permiten archivos JPG, JPEG, PNG o WEBP.")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})

        # 3. VALIDACIÓN: Dirección (Mínimo 10 y máximo 150 caracteres)
        if len(direccion) < 10 or len(direccion) > 150:
            messages.error(request, "La dirección debe ser clara y detallada (entre 10 y 150 caracteres).")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})

        # 4. VALIDACIÓN: Capacidad Máxima (Entero mayor a cero)
        try:
            capacidad_maxima = int(capacidad_raw)
            if capacidad_maxima <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "La capacidad máxima debe ser un número entero mayor a cero.")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})

        # 5. VALIDACIÓN: Costo de Renta (Entero mayor a cero)
        try:
            precio_renta = int(precio_raw)
            if precio_renta <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "El costo de renta debe ser un número entero superior a cero.")
            return render(request, 'Lugar/crear.html', {'valores_previos': valores_previos})

        # Si todo está en orden, guardamos en la BD
        Lugar.objects.create(
            nombre=nombre,
            direccion=direccion,
            capacidad_maxima=capacidad_maxima,
            precio_renta=precio_renta,
            imagen=imagen,
            estado='A'
        )

        messages.success(request, f"La locación '{nombre}' ha sido registrada con éxito en el catálogo.")
        return redirect('gestionar_catalogos')

    return render(request, 'Lugar/crear.html')

def pre_editar_lugar(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    lugar = Lugar.objects.get(id=id)
    return render(request, 'Lugar/editar.html', {
        'lugar': lugar
    })

def editar_lugar(request):
    if request.method == "POST":
        id_lugar = request.POST.get('txt_id')
        nombre = request.POST.get('txt_nombre', '').strip()
        direccion = request.POST.get('txt_direccion', '').strip()
        capacidad_raw = request.POST.get('txt_capacidad_maxima', '').strip()
        precio_raw = request.POST.get('txt_precio_renta', '').strip()
        estado = request.POST.get('txt_estado')

        # Control de existencia de la locación
        try:
            lugar = Lugar.objects.get(id=id_lugar)
        except Lugar.DoesNotExist:
            messages.error(request, "La locación que intenta editar no existe en la base de datos.")
            return redirect('gestionar_catalogos')

        # Hidratamos el objeto de manera temporal para retener los datos en el front en caso de error
        lugar.nombre = nombre
        lugar.direccion = direccion
        lugar.capacidad_maxima = capacidad_raw
        lugar.precio_renta = precio_raw
        lugar.estado = estado

        # 1. VALIDACIÓN: Nombre de la Sede (Alfanumérico de 3 a 60 caracteres)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ0-9\s]{3,60}$', nombre):
            messages.error(request, "Error: El nombre de la sede debe ser alfanumérico y contener entre 3 y 60 caracteres.")
            return render(request, 'Lugar/editar.html', {'lugar': lugar})

        # 2. VALIDACIÓN: Dirección (Mínimo 10 y máximo 150 caracteres)
        if len(direccion) < 10 or len(direccion) > 150:
            messages.error(request, "Error: La ubicación requiere una descripción clara (entre 10 y 150 caracteres).")
            return render(request, 'Lugar/editar.html', {'lugar': lugar})

        # 3. VALIDACIÓN: Capacidad Máxima (Entero positivo mayor a 0)
        try:
            capacidad_maxima = int(capacidad_raw)
            if capacidad_maxima <= 0:
                raise ValueError
            lugar.capacidad_maxima = capacidad_maxima
        except ValueError:
            messages.error(request, "Error: La capacidad del salón debe ser un número entero estrictamente mayor a cero.")
            return render(request, 'Lugar/editar.html', {'lugar': lugar})

        # 4. VALIDACIÓN: Costo de Renta (Entero limpio positivo)
        try:
            precio_renta = int(precio_raw)
            if precio_renta <= 0:
                raise ValueError
            lugar.precio_renta = precio_renta
        except ValueError:
            messages.error(request, "Error: El costo de renta mensual/diario debe ser un número entero mayor a cero.")
            return render(request, 'Lugar/editar.html', {'lugar': lugar})

        # Pasadas las compuertas de seguridad, se ejecuta el guardado definitivo
        lugar.save()
        messages.success(request, f"Locación '{nombre}' actualizada correctamente.")
        
    return redirect('gestionar_catalogos')

def eliminar_lugar(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    lugar = Lugar.objects.get(id=id)
    lugar.estado = "I"
    lugar.save()
    return redirect('gestionar_catalogos')

def habilitar_lugar(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    lugar = Lugar.objects.get(id=id)
    lugar.estado = "A"
    lugar.save()
    return redirect('gestionar_catalogos')


def cambiar_estado_catalogo(request, tipo, id): 
    if tipo == 'servicio': obj = Servicio.objects.get(id=id) 
    elif tipo == 'menu': obj = MenuComida.objects.get(id=id) 
    elif tipo == 'lugar': obj = Lugar.objects.get(id=id) 
    else: return redirect('dashboard_admin') 
    # Lógica de cambio de estado 
    obj.estado = 'I' if obj.estado == 'A' else 'A' 
    obj.save() 
    # Redirigir a la página anterior 
    
    return redirect(request.META.get('HTTP_REFERER', 'dashboard_admin'))
