import re

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from decimal import Decimal
from datetime import datetime
from django.db.models import Count
from django.db.models import Sum, F, Q
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from weasyprint import HTML
from inventario.models import Producto, MovimientoProducto
import datetime

import os
import pandas as pd
from django.contrib import messages
from django.core.files import File
from django.conf import settings


# Create your views here.

#////////////////////    REPORTE DE LOS PRODUCTOS     ////////////////////

def exportar_productos_pdf(request):
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    # --- FILTROS ---
    query = request.GET.get('q', '')
    solo_stock_bajo = request.GET.get('bajo_stock') == 'on'
    
    productos_base = Producto.objects.filter(estado="A")

    if query:
        productos_base = productos_base.filter(Q(nombre_producto__icontains=query) | Q(id__icontains=query))
    if solo_stock_bajo:
        productos_base = productos_base.filter(stock_disponible__lt=5)

    productos_base = productos_base.order_by('-stock_disponible')

    # --- CÁLCULOS GERENCIALES ---
    # Calculamos la valorización total del inventario filtrado
    valor_total = sum(p.stock_disponible * p.precio_alquiler for p in productos_base)
    
    # Preparamos los productos con sus subtotales para el PDF
    lista_productos = []
    for p in productos_base:
        p.subtotal = p.stock_disponible * p.precio_alquiler
        lista_productos.append(p)

    # Lógica para la Gráfica de Salud (Top 10)
    top_10_grafico = []
    for p in productos_base[:10]:
        porcentaje = (p.stock_disponible * 100) / p.stock_total if p.stock_total > 0 else 0
        top_10_grafico.append({
            'nombre': p.nombre_producto,
            'porcentaje': min(porcentaje, 100),
            'disponible': p.stock_disponible,
        })

    context = {
        'productos': lista_productos,
        'top_10_grafico': top_10_grafico,
        'valor_total': valor_total,
        'stock_bajo': productos_base.filter(stock_disponible__lt=5).count(),
        'fecha': datetime.datetime.now(),
        'generado_por': request.session.get('nombre_usuario', 'Administrador'),
        'filtros': {
            'busqueda': query,
            'solo_bajo': solo_stock_bajo,
        }
    }
    
    html_string = render_to_string('Producto/reporte_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Reporte_Gerencial_Aaron.pdf"'
    
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response


def reporte_productos(request):
    productos = Producto.objects.all().order_by('nombre')
    
    valor_total = sum(p.stock * p.precio_unitario for p in productos)
    stock_bajo = productos.filter(stock__lt=5).count()

    # Datos para gráficas
    data_cat = Producto.objects.values('categoria__nombre').annotate(total=Count('id'))
    
    context = {
        'productos': productos,
        'valor_total': valor_total,
        'stock_bajo': stock_bajo,
        'categorias_labels': [c['categoria__nombre'] or "General" for c in data_cat],
        'categorias_counts': [c['total'] for c in data_cat],
    }

    return render(request, 'Reserva/reporte_productos.html', context)



#////////////////////    GESTION DE LOS PRODUCTOS     ////////////////////

def listar_productos(request):
    #Lista
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    productos_activos = Producto.objects.filter(estado="A")
    productos_inactivos = Producto.objects.filter(estado="I")
    
    return render(request, 'Producto/index.html', {
        'productos': productos_activos,
        'productos_inactivos': productos_inactivos
    })


def mostrar_registro_producto(request):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    return render(request, 'Producto/crear.html')


def registrar_producto(request):
    if request.method == 'POST':
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        p_compra_raw = request.POST.get('txt_precio_compra', '0')
        p_alquiler_raw = request.POST.get('txt_precio_alquiler', '0')
        stock_raw = request.POST.get('txt_stock_total', '0')
        imagen = request.FILES.get('txt_imagen')

        # Regex para validar alfanumérico adaptado al español
        pattern = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,.\-]+$'

        # 1. Validaciones del Nombre
        if len(nombre) < 3 or len(nombre) > 30:
            messages.error(request, "Error: El nombre debe tener entre 3 y 30 caracteres.")
            return redirect('mostrar_registro_producto')
        if not re.match(pattern, nombre):
            messages.error(request, "Error: El nombre contiene caracteres inválidos.")
            return redirect('mostrar_registro_producto')

        # 2. Validaciones de la Descripción
        if len(descripcion) < 25 or len(descripcion) > 350:
            messages.error(request, "Error: La descripción debe tener entre 25 y 350 caracteres.")
            return redirect('mostrar_registro_producto')
        if not re.match(pattern, descripcion):
            messages.error(request, "Error: La descripción contiene caracteres especiales inválidos.")
            return redirect('mostrar_registro_producto')

        # 3. Validaciones Numéricas (Conversión Segura a Enteros)
        try:
            p_compra = int(float(p_compra_raw))
            p_alquiler = int(float(p_alquiler_raw))
            stock = int(float(stock_raw))
            
            if p_compra < 0 or p_alquiler < 0 or stock < 0:
                raise ValueError()
        except ValueError:
            messages.error(request, "Error: Los precios y el stock deben ser números enteros no negativos.")
            return redirect('mostrar_registro_producto')

        # 4. Validación de Imagen Obligatoria
        if not imagen:
            messages.error(request, "Error: La imagen del producto es obligatoria.")
            return redirect('mostrar_registro_producto')

        # Si todo el filtro pasa con éxito, se persiste en base de datos
        Producto.objects.create(
            nombre_producto=nombre,
            descripcion=descripcion,
            precio_compra=p_compra,
            precio_alquiler=p_alquiler,
            stock_total=stock,
            stock_disponible=stock,
            estado='A',
            imagen=imagen
        )

        messages.success(request, f"Producto '{nombre}' registrado exitosamente.")
        return redirect('listar_productos')

    # Si es un método GET u otro, redirige al formulario limpio
    # Nota: Asegúrate de mapear bien esta ruta en tus URLs
    return render(request, 'Producto/crear.html')

def mostrar_detalle_producto(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
    
    producto = Producto.objects.get(id=id)
    return render(request, 'Producto/consultar.html', {
        'producto': producto
    })


def pre_editar_producto(request, id):
    #Formulario
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    producto = Producto.objects.get(id=id)
    return render(request, 'Producto/editar.html', {
        'producto': producto
    })


def editar_producto(request):
    if request.method == 'POST':
        id_producto = request.POST.get('txt_id')
        nombre = request.POST.get('txt_nombre', '').strip()
        descripcion = request.POST.get('txt_descripcion', '').strip()
        p_compra_raw = request.POST.get('txt_precio_compra', '0')
        p_alquiler_raw = request.POST.get('txt_precio_alquiler', '0')
        estado = request.POST.get('txt_estado')
        stock_t_raw = request.POST.get('txt_stock_total', '0')
        stock_d_raw = request.POST.get('txt_stock_disponible', '0')
        imagen = request.FILES.get('txt_imagen')

        # Buscar el producto existente de forma segura
        producto = get_object_or_404(Producto, id=id_producto)

        # Regla de expresiones regulares para caracteres en español
        pattern = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,.\-]+$'

        # 1. Filtros de longitud y caracteres para textos
        if len(nombre) < 3 or len(nombre) > 30 or not re.match(pattern, nombre):
            messages.error(request, "Error: Nombre inválido o fuera del rango (3-30 caracteres).")
            return redirect('listar_productos')

        if len(descripcion) < 25 or len(descripcion) > 350 or not re.match(pattern, descripcion):
            messages.error(request, "Error: Descripción operativa fuera del rango permitido (25-350 caracteres).")
            return redirect('listar_productos')

        # 2. Conversiones numéricas seguras
        try:
            p_compra = int(float(p_compra_raw))
            p_alquiler = int(float(p_alquiler_raw))
            stock_t = int(float(stock_t_raw))
            stock_d = int(float(stock_d_raw))

            if p_compra < 0 or p_alquiler < 0 or stock_t < 0 or stock_d < 0:
                raise ValueError()
        except ValueError:
            messages.error(request, "Error: Los precios y cantidades deben ser números enteros válidos y no negativos.")
            return redirect('listar_productos')

        # 3. Validación lógica del Stock
        if stock_d > stock_t:
            messages.error(request, f"Error: El stock disponible ({stock_d}) no puede ser mayor que el stock total ({stock_t}).")
            return redirect('listar_productos')

        # Si todo pasa las restricciones, actualizamos las propiedades del objeto
        producto.nombre_producto = nombre
        producto.descripcion = descripcion
        producto.precio_compra = p_compra
        producto.precio_alquiler = p_alquiler
        producto.estado = estado
        producto.stock_total = stock_t
        producto.stock_disponible = stock_d

        # Actualizar la foto solo si el usuario seleccionó un nuevo archivo
        if imagen:
            producto.imagen = imagen

        producto.save()
        messages.success(request, f"Producto '{nombre}' actualizado correctamente en el sistema.")
        
    return redirect('listar_productos')


def eliminar_producto(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    producto = Producto.objects.get(id=id)
    producto.estado = "I"
    producto.save()
    return redirect('listar_productos')


def habilitar_producto(request, id):

    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")
        
    producto = Producto.objects.get(id=id)
    producto.estado = "A"
    producto.save()
    return redirect('listar_productos')



#////////////////////    REGISTRO DE LOS MOVIMIENTOS DE PRODUCTOS     ////////////////////

def listar_movimientos(request):
    # Traemos absolutamente todos los movimientos de Arron Eventos
    movimientos = MovimientoProducto.objects.all().select_related(
        'producto', 'alquiler', 'reserva'
    ).order_by('-fecha')
    
    return render(request, 'Producto/movimientos.html', {'movimientos': movimientos})


def interfaz_registro_manual(request):
    """
    Muestra la lista de productos activos para ejecutar operaciones de Compra o Daño.
    Mapeada a: {% url 'interfaz_registro_manual' %}
    """
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    # Obtenemos únicamente productos activos para evitar ajustes sobre mercancía dada de baja
    productos_listado = Producto.objects.filter(estado="A").order_by('nombre_producto')
    
    return render(request, 'Producto/registro_movimiento_manual.html', {
        'productos_listado': productos_listado
    })


@require_POST
def registrar_movimiento_manual(request):
    """
    Procesa el formulario POST enviado desde el modal de ajustes manuales con validaciones de seguridad.
    """
    if "usuario_id" not in request.session:
        return redirect("iniciar_sesion")

    producto_id = request.POST.get('producto_id')
    tipo_movimiento = request.POST.get('tipo_movimiento')  # Recibe: 'COMPRA' o 'DANO'
    observacion = request.POST.get('observacion', '').strip()
    
    # 1. Validación de cantidad entera y positiva
    try:
        cantidad = int(request.POST.get('cantidad', 0))
        if cantidad <= 0:
            messages.error(request, "Error: La cantidad de unidades debe ser un número entero mayor a cero.")
            return redirect('movimientos_producto')
    except (ValueError, TypeError):
        messages.error(request, "Error: La cantidad ingresada no es válida.")
        return redirect('movimientos_producto')

    producto = get_object_or_404(Producto, id=producto_id)
    
    try:
        if tipo_movimiento == 'COMPRA':
            # Validación de precio de compra válido y no negativo
            try:
                precio_compra_nuevo = int(float(request.POST.get('precio_compra', 0)))
                if precio_compra_nuevo < 0:
                    messages.error(request, "Error: El precio de compra no puede ser un valor negativo.")
                    return redirect('movimientos_producto')
            except (ValueError, TypeError):
                messages.error(request, "Error: El precio de compra ingresado no es un formato válido.")
                return redirect('movimientos_producto')
            
            # Modificar stocks en cascada (Suma)
            producto.stock_total += cantidad
            producto.stock_disponible += cantidad
            
            # Recalcular precio de alquiler automáticamente si cambió el costo base
            if precio_compra_nuevo != producto.precio_compra:
                producto.precio_compra = precio_compra_nuevo
                # Regla de negocio de Arron Eventos: El alquiler representa el 15% del costo de adquisición
                producto.precio_alquiler = int(precio_compra_nuevo * 0.15)
            
            producto.save()
            
            # Insertar el registro histórico en MovimientoProducto
            MovimientoProducto.objects.create(
                producto=producto,
                tipo='COMPRA',
                cantidad=cantidad,
                observacion=observacion
            )
            messages.success(request, f"Abastecimiento registrado. Se sumaron {cantidad} unidades a '{producto.nombre_producto}'.")
            
        elif tipo_movimiento == 'DANO':
            # Validación lógica crítica: No dar de baja más unidades de las disponibles físicamente
            if cantidad > producto.stock_disponible:
                messages.error(request, f"Error: No puedes reportar {cantidad} unidades dañadas porque solo hay {producto.stock_disponible} disponibles.")
                return redirect('movimientos_producto')
            
            # Modificar stocks en cascada (Resta)
            producto.stock_total -= cantidad
            producto.stock_disponible -= cantidad
            producto.save()
            
            # Insertar el registro histórico en MovimientoProducto
            MovimientoProducto.objects.create(
                producto=producto,
                tipo='AJUSTE_DANO',
                cantidad=cantidad,
                observacion=observacion
            )
            messages.success(request, f"Baja por daño interno procesada con éxito para '{producto.nombre_producto}'.")
        else:
            messages.error(request, "Error: Operación de inventario no permitida.")
            
    except Exception as e:
        messages.error(request, f"Error imprevisto en la base de datos de inventario: {str(e)}")

    return redirect('movimientos_producto')



#////////////////////    PRODUCTOS QUE VE EL CLIENTE     ////////////////////

def productos_catalogo(request):

    productos = Producto.objects.filter(
    estado='A',
    stock_disponible__gt=0
    )

    return render(request, 'productos_catalogo.html', {
        'productos': productos
    })


#////////////////////    SUPER CARGA DE PRODUCTOS DESDE CSV     ////////////////////

def ejecutar_super_carga(request):
    # Definir rutas basadas en la ubicación del proyecto
    ruta_csv = os.path.join(settings.BASE_DIR, 'data_productos_arrons')
    ruta_fotos = os.path.join(settings.BASE_DIR, 'fotos_ipercarga')
    extensiones_validas = ['.jpg', '.png', '.jpeg', '.JPG', '.PNG', '.JPEG']

    if not os.path.exists(ruta_csv):
        messages.error(request, f'❌ No se encuentra la carpeta: {ruta_csv}')
        return redirect('tu_url_de_inventario') # Cambia esto por el nombre de tu url de lista

    archivos_csv = [f for f in os.listdir(ruta_csv) if f.endswith('.csv')]
    creados = 0
    omitidos = 0

    for archivo in archivos_csv:
        df = pd.read_csv(os.path.join(ruta_csv, archivo))
        
        for _, f in df.iterrows():
            # get_or_create: busca por nombre, si no existe usa defaults
            obj, created = Producto.objects.get_or_create(
                nombre_producto=f['nombre'],
                defaults={
                    'descripcion': f['desc'],
                    'precio_compra': f['compra'],
                    'precio_alquiler': f['alquiler'],
                    'stock_total': f['stock'],
                    'stock_disponible': f['stock'],
                    'estado': 'A'
                }
            )

            if created:
                creados += 1
                # Lógica de imagen
                nombre_base = os.path.splitext(str(f['imagen']))[0].strip()
                
                for ext in extensiones_validas:
                    posible_ruta = os.path.join(ruta_fotos, nombre_base + ext)
                    if os.path.exists(posible_ruta):
                        with open(posible_ruta, 'rb') as doc:
                            obj.imagen.save(nombre_base + ext, File(doc), save=True)
                        break
            else:
                omitidos += 1

    messages.success(request, f"🚀 Super Carga: {creados} nuevos, {omitidos} omitidos.")
    return redirect(request.META.get('HTTP_REFERER', 'listar_productos')) 