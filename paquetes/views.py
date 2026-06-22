import re

from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal
from django.contrib import messages
from .models import Paquete, PaqueteProducto, PaqueteServicio, Servicio
from inventario.models import Producto

# Create your views here.

#////////////////////    PAQUETES QUE PUEDE VER EL CLIENTE     ////////////////////

def paquetes_catalogo(request):

    paquetes = Paquete.objects.filter(
        estado='A'
    ).prefetch_related(
        'paqueteproducto_set',
        'paqueteservicio_set'
    )

    return render(request, 'paquetes_catalogo.html', {
        'paquetes': paquetes
    })



#////////////////////    GESTION DE LOS PAQUETES     ////////////////////

def listar_paquetes(request):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    paquetes = Paquete.objects.filter(estado="A")
    paquetes_inactivos = Paquete.objects.filter(estado="I")

    return render(request, "Paquete/index.html", {
        "paquetes": paquetes,
        "paquetes_inactivos": paquetes_inactivos
    })

def mostrar_registro_paquete(request):
    #Formulario
    productos = Producto.objects.filter(estado='A')
    servicios = Servicio.objects.filter(estado='A')

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    return render(request, 'Paquete/crear.html', {
        'productos': productos,
        'servicios': servicios
    })

def registrar_paquete(request):
    if request.method == "POST":
        # 1. Capturar datos básicos del formulario
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        duracion_str = request.POST.get('txt_duracion_horas', '0')

        productos_ids = request.POST.getlist('productosIds')
        servicios_ids = request.POST.getlist('serviciosIds')

        # 2. Traer listas completas de la base de datos para el reporte de error
        productos_lista = Producto.objects.all()
        servicios_lista = Servicio.objects.all()

        # ASIGNACIÓN TEMPORAL: Metemos la cantidad digitada dentro de cada producto 
        # para que el HTML la recuerde de forma directa sin usar filtros complejos.
        for p in productos_lista:
            if str(p.id) in productos_ids:
                p.cantidad_temporal = request.POST.get(f'cantidades_prod_{p.id}', '')

        # Estructuramos el contexto que se devolverá si alguna validación falla
        contexto_error = {
            'productos': productos_lista,
            'servicios': servicios_lista,
            'seleccionados_prod': productos_ids,
            'seleccionados_serv': servicios_ids,
            'datos': {
                'nombre': nombre,
                'descripcion': descripcion,
                'duracion': duracion_str
            }
        }

        # --- SECCIÓN DE VALIDACIONES STRICT DE ARRON ---

        # A. Validaciones del Nombre
        if len(nombre) < 15 or len(nombre) > 60:
            contexto_error['error'] = "El nombre del paquete debe tener entre 15 y 60 caracteres."
            return render(request, 'Paquete/crear.html', contexto_error)

        if not re.match(r'^[a-zA-ZÁÉÍÓÚÑáéíóúñ\s]+$', nombre):
            contexto_error['error'] = "El nombre del paquete solo puede contener letras y espacios."
            return render(request, 'Paquete/crear.html', contexto_error)

        if Paquete.objects.filter(nombre__iexact=nombre).exists():
            contexto_error['error'] = f"Ya existe un paquete registrado con el nombre '{nombre}'."
            return render(request, 'Paquete/crear.html', contexto_error)

        # B. Validaciones de la Descripción
        if len(descripcion) < 20 or len(descripcion) > 250:
            contexto_error['error'] = "La descripción debe tener entre 20 y 250 caracteres."
            return render(request, 'Paquete/crear.html', contexto_error)

        # C. Validaciones de la Duración
        try:
            duracion = int(duracion_str)
            if duracion < 2 or duracion > 15:
                contexto_error['error'] = "La duración debe estar entre las 2 y las 15 horas máximo."
                return render(request, 'Paquete/crear.html', contexto_error)
        except ValueError:
            contexto_error['error'] = "La duración introducida debe ser un número entero válido."
            return render(request, 'Paquete/crear.html', contexto_error)

        # 🆕 VALIDACIÓN CRÍTICA: Al menos un producto seleccionado
        if not productos_ids:
            contexto_error['error'] = "Debes seleccionar al menos un producto del inventario para poder crear el paquete."
            return render(request, 'Paquete/crear.html', contexto_error)

        # D. Validaciones de Cantidades del Inventario
        for pid in productos_ids:
            cant_str = request.POST.get(f'cantidades_prod_{pid}', '0')
            try:
                cantidad = int(cant_str or 0)
                if cantidad < 1:
                    contexto_error['error'] = "Cada producto seleccionado debe tener una cantidad mínima de 1."
                    return render(request, 'Paquete/crear.html', contexto_error)
            except ValueError:
                contexto_error['error'] = "Las cantidades de los productos deben ser números enteros."
                return render(request, 'Paquete/crear.html', contexto_error)


        # --- PROCESO DE CÁLCULO FINAL Y GUARDADO SEGURO ---
        try:
            total = 0

            # Sumar precios de productos seleccionados
            for pid in productos_ids:
                cantidad = int(request.POST.get(f'cantidades_prod_{pid}') or 0)
                if cantidad > 0:
                    producto = Producto.objects.get(id=pid)
                    total += producto.precio_alquiler * cantidad

            # Sumar precios de servicios agregados
            for sid in servicios_ids:
                servicio = Servicio.objects.get(id=sid)
                total += servicio.precio_servicio

            # Cálculo automático del 15% de depósito
            deposito = total * Decimal('0.15')

            # 1. Crear el paquete maestro
            paquete = Paquete.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                duracion_horas=duracion,
                precio=total,
                deposito_garantia=deposito,
                estado='A'
            )

            # 2. Registrar la relación de productos con sus cantidades
            for pid in productos_ids:
                cantidad = int(request.POST.get(f'cantidades_prod_{pid}') or 0)
                if cantidad > 0:
                    PaqueteProducto.objects.create(
                        paquete=paquete,
                        producto_id=pid,
                        cantidad=cantidad
                    )

            # 3. Registrar la relación de servicios vinculados
            for sid in servicios_ids:
                PaqueteServicio.objects.create(
                    paquete=paquete,
                    servicio_id=sid
                )

            return redirect('listar_paquetes')

        except Exception as e:
            contexto_error['error'] = f"Error crítico al guardar en el sistema: {e}"
            return render(request, 'Paquete/crear.html', contexto_error)

    # Carga limpia de la página por método GET
    contexto_inicial = {
        'productos': Producto.objects.all(),
        'servicios': Servicio.objects.all()
    }
    return render(request, 'Paquete/crear.html', contexto_inicial)


def mostrar_detalle_paquete(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    
    paquete = Paquete.objects.get(id=id)
    return render(request, 'Paquete/consultar.html', {
        'paquete': paquete
    })

def pre_editar_paquete(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    paquete = Paquete.objects.get(id=id)
    productos = Producto.objects.filter(estado='A')
    servicios = Servicio.objects.filter(estado='A')

    return render(request, 'Paquete/editar.html', {
        'paquete': paquete,
        'productos': productos,
        'servicios': servicios
    })

def editar_paquete(request, id):
    paquete = get_object_or_404(Paquete, id=id)
    productos = Producto.objects.all()
    servicios = Servicio.objects.all()

    if request.method == "POST":
        # 1. Capturar datos del formulario
        nombre = request.POST.get("txt_nombre", "").strip()
        descripcion = request.POST.get("txt_descripcion", "").strip()
        duracion_str = request.POST.get("txt_duracion_horas", "0")

        productos_ids = request.POST.getlist("productos_ids")
        servicios_ids = request.POST.getlist("servicios_ids")

        # 2. Persistencia temporal en memoria por si hay errores de validación
        for p in productos:
            p.seleccionado = str(p.id) in productos_ids
            p.cantidad = request.POST.get(f"cantidades_productos_{p.id}", "")

        for s in servicios:
            s.seleccionado = str(s.id) in servicios_ids

        # Armamos el contexto de retorno ante fallas
        contexto_error = {
            "paquete": paquete,
            "productos": productos,
            "servicios": servicios,
            "productos_seleccionados": set(int(x) for x in productos_ids),
            "servicios_seleccionados": set(int(x) for x in servicios_ids),
            # Pisamos los datos originales del paquete en el HTML con lo que envió el usuario
            "datos_editados": {
                "nombre": nombre,
                "descripcion": descripcion,
                "duracion_horas": duracion_str
            }
        }

        # --- SECCIÓN DE VALIDACIONES STRICT DE ARRON ---

        # A. Validaciones del Nombre (Excluyendo el ID actual)
        if len(nombre) < 15 or len(nombre) > 60:
            contexto_error['error'] = "El nombre del paquete debe tener entre 15 y 60 caracteres."
            return render(request, "Paquete/editar.html", contexto_error)

        if not re.match(r'^[a-zA-ZÁÉÍÓÚÑáéíóúñ\s]+$', nombre):
            contexto_error['error'] = "El nombre del paquete solo puede contener letras y espacios."
            return render(request, "Paquete/editar.html", contexto_error)

        if Paquete.objects.filter(nombre__iexact=nombre).exclude(id=paquete.id).exists():
            contexto_error['error'] = f"Ya existe otro paquete registrado con el nombre '{nombre}'."
            return render(request, "Paquete/editar.html", contexto_error)

        # B. Validaciones de la Descripción
        if len(descripcion) < 20 or len(descripcion) > 250:
            contexto_error['error'] = "La descripción debe tener entre 20 y 250 caracteres."
            return render(request, "Paquete/editar.html", contexto_error)

        # C. Validaciones de la Duración
        try:
            duracion = int(duracion_str)
            if duracion < 2 or duracion > 15:
                contexto_error['error'] = "La duración debe estar entre las 2 y las 15 horas máximo."
                return render(request, "Paquete/editar.html", contexto_error)
        except ValueError:
            contexto_error['error'] = "La duración introducida debe ser un número entero válido."
            return render(request, "Paquete/editar.html", contexto_error)

        # 🆕 VALIDACIÓN CRÍTICA: Al menos un producto seleccionado
        if not productos_ids:
            contexto_error['error'] = "Debes seleccionar al menos un producto del inventario para poder actualizar el paquete."
            return render(request, "Paquete/editar.html", contexto_error)

        # D. Validaciones de Cantidades del Inventario
        for pid in productos_ids:
            cant_str = request.POST.get(f"cantidades_productos_{pid}", "0")
            try:
                cantidad = int(cant_str or 0)
                if cantidad < 1:
                    contexto_error['error'] = "Cada producto seleccionado debe tener una cantidad mínima de 1."
                    return render(request, "Paquete/editar.html", contexto_error)
            except ValueError:
                contexto_error['error'] = "Las cantidades de los productos deben ser números enteros."
                return render(request, "Paquete/editar.html", contexto_error)

        # --- GUARDADO PROGRESIVO Y SEGURO ---
        try:
            # Asignamos los valores validados al objeto maestro
            paquete.nombre = nombre
            paquete.descripcion = descripcion
            paquete.duracion_horas = duracion
            paquete.save()

            # Reestablecer Relación de Productos
            PaqueteProducto.objects.filter(paquete=paquete).delete()
            for pid in productos_ids:
                cantidad = int(request.POST.get(f"cantidades_productos_{pid}", 1))
                PaqueteProducto.objects.create(
                    paquete=paquete,
                    producto_id=pid,
                    cantidad=cantidad
                )

            # Reestablecer Relación de Servicios
            PaqueteServicio.objects.filter(paquete=paquete).delete()
            for sid in servicios_ids:
                PaqueteServicio.objects.create(
                    paquete=paquete,
                    servicio_id=sid
                )

            # Recalculamos precios y depósitos consolidados
            paquete.calcular_precio()

            return redirect("mostrar_detalle_paquete", paquete.id)

        except Exception as e:
            contexto_error['error'] = f"Error crítico al actualizar en el sistema: {e}"
            return render(request, "Paquete/editar.html", contexto_error)

    # -------- RENDEREADO POR GET (CARGA INICIAL) --------
    productos_paquete = PaqueteProducto.objects.filter(paquete=paquete)
    productos_seleccionados = set(pp.producto_id for pp in productos_paquete)
    servicios_seleccionados = set(PaqueteServicio.objects.filter(paquete=paquete).values_list("servicio_id", flat=True))

    cantidades = {pp.producto_id: pp.cantidad for pp in productos_paquete}

    for p in productos:
        if p.id in cantidades:
            p.cantidad = cantidades[p.id]
            p.seleccionado = True
        else:
            p.cantidad = ""
            p.seleccionado = False

    for s in servicios:
        s.seleccionado = s.id in servicios_seleccionados

    context = {
        "paquete": paquete,
        "productos": productos,
        "servicios": servicios,
        "productos_seleccionados": productos_seleccionados,
        "servicios_seleccionados": servicios_seleccionados
    }
    return render(request, "Paquete/editar.html", context)


def eliminar_paquete(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    paquete = Paquete.objects.get(id=id)
    paquete.estado = "I"
    paquete.save()
    return redirect('listar_paquetes')

def activar_paquete(request, id):

    paquete = get_object_or_404(Paquete, id=id)

    paquete.estado = "A"
    paquete.save()

    return redirect("listar_paquetes")


#////////////////////    GESTION DE LOS SERVICIOS     ////////////////////

def mostrar_registro_servicio(request):
    #Formulario

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    return render(request, 'Servicio/crear.html')

def registrar_servicio(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    if request.method == "POST":
        # Captura de campos tradicionales
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        precio_raw = request.POST.get('txt_precio', '').strip()

        # === CAPTURA DE LOS NUEVOS CAMPOS EXTENDIDOS ===
        empresa_externa = request.POST.get('txt_empresa_externa', '').strip()
        nombre_proveedor = request.POST.get('txt_nombre_proveedor', '').strip()
        telefono_proveedor = request.POST.get('txt_telefono_proveedor', '').strip()
        nit_proveedor = request.POST.get('txt_nit_proveedor', '').strip()
        costo_proveedor_raw = request.POST.get('txt_costo_proveedor', '0').strip()

        # Almacenamos todos los valores previos por si toca recargar la vista debido a un error
        valores_previos = {
            'nombre': nombre,
            'descripcion': descripcion,
            'precio': precio_raw,
            'empresa_externa': empresa_externa,
            'nombre_proveedor': nombre_proveedor,
            'telefono_proveedor': telefono_proveedor,
            'nit_proveedor': nit_proveedor,
            'costo_proveedor': costo_proveedor_raw
        }

        # 1. VALIDACIÓN: Nombre del Servicio (Letras y espacios, 2 a 50 caracteres)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre):
            messages.error(request, "El nombre del servicio debe ser estrictamente alfabético y tener entre 2 y 50 caracteres.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # 2. VALIDACIÓN: Descripción (Longitud entre 20 y 250 caracteres)
        if len(descripcion) < 20 or len(descripcion) > 250:
            messages.error(request, "La descripción debe tener una extensión obligatoria de entre 20 y 250 caracteres.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # 3. VALIDACIÓN: Costo de Venta al Cliente (Entero positivo)
        try:
            precio = int(precio_raw)
            if precio <= 0:  # Cambiado a <= 0 porque cobrar $0 por un servicio no tendría sentido comercial
                raise ValueError
        except ValueError:
            messages.error(request, "El precio del servicio al cliente debe ser un número entero válido mayor a cero.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # ==============================================================================
        # NUEVAS VALIDACIONES DE SEGURIDAD PARA EL PROVEEDOR EXTERNO
        # ==============================================================================

        # 4. VALIDACIÓN: Nombre del Especialista / Responsable (Misma regex del nombre de servicio)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre_proveedor):
            messages.error(request, "El nombre del especialista/proveedor debe ser alfabético y tener entre 2 y 50 caracteres.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # 5. VALIDACIÓN: Teléfono de Contacto (Solo números, entre 7 y 15 dígitos para fijos o celulares)
        if not re.match(r'^\d{7,15}$', telefono_proveedor):
            messages.error(request, "El teléfono de contacto debe contener únicamente números y tener entre 7 y 15 dígitos.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # 6. VALIDACIÓN: NIT o Cédula (Alfanumérico con guiones permitidos opcionalmente, ej: 901234567-1 o 1023456)
        if not re.match(r'^[A-Za-z0-9\-]{5,20}$', nit_proveedor):
            messages.error(request, "El documento Identificador/NIT del proveedor no es válido (Debe tener entre 5 y 20 caracteres).")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # 7. VALIDACIÓN: Costo del Proveedor (Entero no negativo) y Margen de Utilidad
        try:
            costo_proveedor = int(costo_proveedor_raw)
            if costo_proveedor < 0:
                raise ValueError
            
            # Validación de Regla Logística Crítica: No puedes cobrarle al cliente menos de lo que te cuesta el externo
            if precio < costo_proveedor:
                messages.error(request, "Error Financiero: El precio de venta al cliente no puede ser menor que el costo cobrado por el proveedor.")
                return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})
        except ValueError:
            messages.error(request, "El costo interno del proveedor debe ser un número entero válido no negativo.")
            return render(request, 'Servicio/crear.html', {'valores_previos': valores_previos})

        # Si supera con éxito absolutamente todos los filtros, persistimos la información expandida
        # Ajusta los nombres de los atributos de la derecha si en tu archivo models.py los llamaste diferente
        Servicio.objects.create(
            nombre_servicio=nombre,          # O como esté mapeado en tu modelo original (nombre o nombre_servicio)
            descripcion=descripcion,
            precio_servicio=precio,          # O precio
            nombre_empresa_externa=empresa_externa if empresa_externa else "Independiente",
            nombre_proveedor=nombre_proveedor,
            telefono_proveedor=telefono_proveedor,
            nit_o_cedula_proveedor=nit_proveedor,
            costo_proveedor=costo_proveedor,
            estado='A'
        )
        
        messages.success(request, f"Servicio externo '{nombre}' registrado exitosamente con trazabilidad de proveedor.")
        return redirect('gestionar_catalogos')
        
    return render(request, 'Servicio/crear.html')

def pre_editar_servicio(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    servicio = Servicio.objects.get(id=id)
    return render(request, 'Servicio/editar.html', {
        'servicio': servicio
    })

def editar_servicio(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    if request.method == "POST":
        id_servicio = request.POST.get('txt_id')
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        precio_raw = request.POST.get('txt_precio', '').strip()
        estado = request.POST.get('txt_estado')

        # === NUEVA CAPTURA DE CAMPOS EXTENDIDOS DEL PROVEEDOR ===
        empresa_externa = request.POST.get('txt_empresa_externa', '').strip()
        nombre_proveedor = request.POST.get('txt_nombre_proveedor', '').strip()
        telefono_proveedor = request.POST.get('txt_telefono_proveedor', '').strip()
        nit_proveedor = request.POST.get('txt_nit_proveedor', '').strip()
        costo_proveedor_raw = request.POST.get('txt_costo_proveedor', '0').strip()

        # Buscamos el registro real de la base de datos
        try:
            servicio = Servicio.objects.get(id=id_servicio)
        except Servicio.DoesNotExist:
            messages.error(request, "El servicio que intenta editar no existe.")
            return redirect('gestionar_catalogos')

        # Asignamos temporalmente los datos ingresados al objeto para no perderlos si falla algo
        # Ajusta el nombre de los atributos de la izquierda si en tu models.py difieren
        servicio.nombre_servicio = nombre  # O servicio.nombre según tu modelo original
        servicio.descripcion = descripcion
        servicio.precio_servicio = precio_raw  # Se mantiene la string temporalmente para el renderizado
        servicio.estado = estado
        
        # Asignación temporal de campos del proveedor
        servicio.nombre_empresa_externa = empresa_externa if empresa_externa else "Independiente"
        servicio.nombre_proveedor = nombre_proveedor
        servicio.telefono_proveedor = telefono_proveedor
        servicio.nit_o_cedula_proveedor = nit_proveedor
        servicio.costo_proveedor = costo_proveedor_raw  # Se mantiene string para renderizado por si falla

        # 1. VALIDACIÓN: Nombre alfabético (2 a 50 caracteres)
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre):
            messages.error(request, "Error al actualizar: El nombre del servicio debe poseer solo caracteres alfabéticos (entre 2 y 50 letras).")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # 2. VALIDACIÓN: Descripción (Extensión entre 20 y 250)
        if len(descripcion) < 20 or len(descripcion) > 250:
            messages.error(request, "Error al actualizar: La descripción tiene que cumplir obligatoriamente entre 20 y 250 caracteres.")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # 3. VALIDACIÓN: Tarifa de Venta al Cliente (Entero positivo)
        try:
            precio_valido = int(precio_raw)
            if precio_valido <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Error al actualizar: El costo de venta al cliente debe ser un valor numérico entero mayor a cero.")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # ==============================================================================
        # NUEVAS COMPUERTAS DE VALIDACIÓN: PROVEEDOR EXTERNO
        # ==============================================================================

        # 4. VALIDACIÓN: Nombre del Responsable Técnico
        if not re.match(r'^[A-Za-záéíóúÁÉÍÓÚñÑ\s]{2,50}$', nombre_proveedor):
            messages.error(request, "Error al actualizar: El nombre del especialista/proveedor debe ser alfabético y tener entre 2 y 50 caracteres.")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # 5. VALIDACIÓN: Teléfono de Contacto (Solo dígitos, entre 7 y 15)
        if not re.match(r'^\d{7,15}$', telefono_proveedor):
            messages.error(request, "Error al actualizar: El teléfono de contacto debe contener únicamente números (entre 7 y 15 dígitos).")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # 6. VALIDACIÓN: Identificación de la Empresa o Persona (NIT / Cédula)
        if not re.match(r'^[A-Za-z0-9\-]{5,20}$', nit_proveedor):
            messages.error(request, "Error al actualizar: El documento o NIT del proveedor no posee un formato alfanumérico válido.")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # 7. VALIDACIÓN: Costo Interno y Margen Financiero
        try:
            costo_proveedor_valido = int(costo_proveedor_raw)
            if costo_proveedor_valido < 0:
                raise ValueError
            
            # Regla Crítica de Control de Pérdidas de Arron Eventos
            if precio_valido < costo_proveedor_valido:
                messages.error(request, "Error Financiero: El precio de venta al cliente no puede ser inferior al costo cobrado por el proveedor externo.")
                return render(request, 'Servicio/editar.html', {'servicio': servicio})
                
        except ValueError:
            messages.error(request, "Error al actualizar: El costo interno del proveedor debe ser un número entero válido no negativo.")
            return render(request, 'Servicio/editar.html', {'servicio': servicio})

        # === CONVERSIÓN Y GUARDADO DEFINITIVO TRAS PASAR LAS VALIDACIONES ===
        servicio.precio_servicio = precio_valido  # O servicio.precio
        servicio.costo_proveedor = costo_proveedor_valido
        servicio.save()
        
        messages.success(request, f"Servicio #{id_servicio} ({nombre}) actualizado correctamente con trazabilidad de proveedor.")
        
    return redirect('gestionar_catalogos')

def eliminar_servicio(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    servicio = Servicio.objects.get(id=id)
    servicio.estado = "I"
    servicio.save()
    return redirect('gestionar_catalogos')

def habilitar_servicio(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    servicio = Servicio.objects.get(id=id)
    servicio.estado = "A"
    servicio.save()
    return redirect('gestionar_catalogos')