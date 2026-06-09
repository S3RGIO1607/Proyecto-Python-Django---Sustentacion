from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Pago, ReservaEvento, Alquiler # Modelos de la misma app
from inventario.models import MovimientoProducto # Modelo de otra app

@receiver(post_save, sender=Pago)
def procesar_pago_y_movimiento(sender, instance, created, **kwargs):
    print(f"¡DEBUG: Signal Pago activado! Creado: {created}")
    
    if created:
        # 1. CASO: RESERVA DE EVENTO
        if instance.reserva:
            reserva = instance.reserva
            print(f"¡DEBUG: Procesando Reserva ID: {reserva.id}!")
            
            if reserva.estado == 'Reservado':
                # --- PASO CRÍTICO: Asegurarnos de que los productos existan ---
                # Si la reserva no tiene productos aún, los generamos del paquete
                if reserva.productos.count() == 0:
                    print("¡DEBUG: Generando productos desde el paquete antes de descontar stock...")
                    reserva.guardar_configuracion_paquete()
                
                reserva.estado = 'Confirmado'
                reserva.save()

                # Ahora sí, buscamos los productos (usando el related_name='productos' que vi en tu modelo)
                productos_reserva = reserva.productos.all() 
                print(f"¡DEBUG: Productos a descontar: {productos_reserva.count()}")

                for rp in productos_reserva:
                    # 1. Registrar Movimiento
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=reserva, # Asociamos el movimiento a la reserva
                        tipo='SALIDA',
                        cantidad=rp.cantidad,
                        observacion=f"Salida por Reserva de Evento #{reserva.id} confirmada"
                    )
                    
                    # 2. Restar Stock directamente
                    prod = rp.producto
                    prod.stock_disponible -= rp.cantidad
                    prod.save()
                    print(f"¡DEBUG: Stock de {prod.nombre_producto} reducido a {prod.stock_disponible}!")

        # 2. CASO: ALQUILER (Este ya te funcionaba)
        elif instance.alquiler:
            alquiler = instance.alquiler
            if alquiler.estado == 'Reservado':
                alquiler.estado = 'Confirmado'
                alquiler.save()

                # Generar SALIDA de inventario y RESTAR STOCK
                for ap in alquiler.alquilerproducto_set.all():
                    # Crear el movimiento (para el historial)
                    MovimientoProducto.objects.create(
                        producto=ap.producto,
                        alquiler=alquiler,
                        tipo='SALIDA',
                        cantidad=ap.cantidad_contratada,
                        observacion=f"Salida por Alquiler #{alquiler.id} confirmado"
                    )

                    # --- LA FORMA DIRECTA QUE BUSCAS ---
                    prod = ap.producto
                    prod.stock_disponible -= ap.cantidad_contratada # Resta simple
                    prod.save() # Guardar el nuevo número en la DB
                    
                    print(f"¡DEBUG: Stock de {prod.nombre_producto} reducido a {prod.stock_disponible}!")