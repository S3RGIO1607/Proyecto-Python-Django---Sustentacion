import datetime as dt_module
from django.db import models
from django.db import models, transaction
from django.core.exceptions import ValidationError
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from urllib3 import request
from django.utils import timezone

from usuarios.models import Usuario
from paquetes.models import Paquete, Servicio
from inventario.models import Producto, MovimientoProducto

# Create your models here.
# ---------------- ALQUILER ----------------

class Alquiler(models.Model):

    ESTADO_CHOICES = [
        ('Reservado', 'Reservado'),
        ('Confirmado', 'Confirmado'),
        ('En Curso', 'En Curso'),
        ('Devuelto', 'Devuelto'),
        ('Finalizado', 'Finalizado'),
        ('Cancelado', 'Cancelado')
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)

    fecha_inicio = models.DateField()
    fecha_devolucion = models.DateField(null=True, blank=True)
    fecha_limite = models.DateField(null=True, blank=True)

    mora_diaria = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10000.00')
    )

    valor_mora = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Reservado'
    )

    incluye_transporte = models.BooleanField(default=False)

    costo_transporte = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    valor_alquiler = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    deposito_garantia = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    valor_danos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    total_final = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    @property
    def saldo_reembolso(self):
        return self.deposito_garantia - self.valor_danos

    def dias_retraso(self):
        if self.fecha_limite and self.fecha_devolucion:
            if self.fecha_devolucion > self.fecha_limite:
                return (self.fecha_devolucion - self.fecha_limite).days

        return 0

    def calcular_mora(self):
        return self.dias_retraso() * self.mora_diaria

    def save(self, *args, **kwargs):
        # fecha límite = fecha inicio + 3 días
        if self.fecha_inicio and not self.fecha_limite:
            self.fecha_limite = self.fecha_inicio + dt_module.timedelta(days=3)

        # calcular mora automática
        self.valor_mora = self.calcular_mora()

        # total final
        self.total_final = (
            self.valor_alquiler +
            self.valor_danos +
            self.deposito_garantia +
            self.costo_transporte +
            self.valor_mora
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Alquiler {self.id} - {self.usuario.nombre}'

# ---------------- ALQUILER PRODUCTO ----------------

class AlquilerProducto(models.Model):

    alquiler = models.ForeignKey(Alquiler, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)

    cantidad_contratada = models.PositiveIntegerField()

    cantidad_retornada_ok = models.PositiveIntegerField(default=0)
    cantidad_danada = models.PositiveIntegerField(default=0)

    precio_alquiler_fijado = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    subtotal_danos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    observacion_dano = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('alquiler', 'producto')

    def __str__(self):
        return f'Alquiler {self.alquiler.id} - {self.producto.nombre_producto}'

# ---------------- RESERVA EVENTO ----------------

class MenuComida(models.Model):

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio_por_persona = models.DecimalField(max_digits=10, decimal_places=2)

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )

    def __str__(self):
        return f"{self.nombre} (${self.precio_por_persona}/pax)"

class Lugar(models.Model):

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    capacidad_maxima = models.PositiveIntegerField()
    precio_renta = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='lugares/', null=True, blank=True)

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )
    novedad = models.TextField(
    blank=True,
    null=True,
    verbose_name="Motivo de la inactivación"
    )

    def __str__(self):
        return f"{self.nombre} (Max: {self.capacidad_maxima})"

class ReservaEvento(models.Model):

    ESTADO_CHOICES = [
        ('Reservado', 'Reservado'),
        ('Confirmado', 'Confirmado'),
        ('En Preparacion', 'En Preparacion'),
        ('Evento Activo', 'Evento Activo'),
        ('Evaluacion', 'Evaluacion'),
        ('Finalizado', 'Finalizado'),
        ('Cancelado', 'Cancelado')
    ]

    ESTADO_DEPOSITO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Retenido', 'Retenido'),
        ('Devuelto', 'Devuelto'),
        ('Usado', 'Usado')
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    menu_comida = models.ForeignKey(MenuComida, on_delete=models.SET_NULL, null=True, blank=True)
    lugar = models.ForeignKey(Lugar, on_delete=models.SET_NULL, null=True, blank=True)

    # =========================================================================
    # NUEVO CAMPO: Vínculo con el Organizador Responsable
    # =========================================================================
    organizador_encargado = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='eventos_supervisados',
        verbose_name="Organizador Encargado"
    )
    # =========================================================================

    fecha_evento = models.DateField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    hora_inicio = models.TimeField(null=True, blank=False) # El cliente la pone
    hora_fin_limpieza = models.DateTimeField(null=True, blank=True, editable=False)

    deposito_garantia = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    asistentes = models.PositiveIntegerField(default=0)

    precio_paquete = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    estado_deposito = models.CharField(
        max_length=20,
        choices=ESTADO_DEPOSITO_CHOICES,
        default='Pendiente'
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Reservado'
    )

    def guardar_configuracion_paquete(self):
        """
        Este método copia los productos y servicios del paquete a la reserva,
        ajustando las cantidades según el número de asistentes.
        """
        if not self.paquete:
            return

        # 1. Calcular el factor de escala (Regla de 3)
        factor = Decimal(self.asistentes) / Decimal(self.paquete.capacidad_base)

        with transaction.atomic():
            # 2. Copiar Productos del Paquete a la Reserva
            for pp in self.paquete.paqueteproducto_set.all():
                cantidad_ajustada = int(pp.cantidad * factor)
                
                ReservaProducto.objects.get_or_create(
                    reserva=self,
                    producto=pp.producto,
                    defaults={
                        'cantidad': cantidad_ajustada,
                        'precio_unitario_fijado': pp.producto.precio_alquiler
                    }
                )

            # 3. Copiar Servicios del Paquete a la Reserva
            for ps in self.paquete.paqueteservicio_set.all():
                ReservaServicio.objects.get_or_create(
                    reserva=self,
                    servicio=ps.servicio,
                    defaults={
                        'precio_fijado': ps.servicio.precio_servicio
                    }
                )

    def clean(self):
        super().clean()
        
        # 1. Validar que tengamos los datos mínimos para comparar
        if not self.fecha_reserva or not self.hora_inicio or not self.hora_fin:
            return

        # Convertir a objetos datetime actuales para validar que no sea en el pasado
        ahora = timezone.localtime(timezone.now())
        fecha_hora_inicio = datetime.combine(self.fecha_reserva, self.hora_inicio)
        
        # Hacer conscientes de zona horaria si usas USE_TZ=True
        if timezone.is_aware(ahora):
            fecha_hora_inicio = timezone.make_aware(fecha_hora_inicio, timezone.get_current_timezone())

        if fecha_hora_inicio < ahora:
            raise ValidationError({'fecha_reserva': "No puedes programar una reserva en una fecha o hora del pasado."})

        # 2. Validar que la hora de fin sea mayor a la de inicio
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': "La hora de finalización debe ser posterior a la hora de inicio."})

        # 3. Calcular la hora de fin de limpieza de manera limpia
        # (Por ejemplo, asumiendo 2 horas de limpieza. Ajusta según tu lógica)
        minutos_limpieza = self.lugar.minutos_limpieza if hasattr(self.lugar, 'minutos_limpieza') else 120
        
        # Truco para sumar tiempo a un time object
        dt_fin = datetime.combine(self.fecha_reserva, self.hora_fin)
        dt_limpieza = dt_fin + timedelta(minutes=minutos_limpieza)
        self.hora_fin_limpieza = dt_limpieza.time()

        # 4. Evitar solapamientos en el mismo lugar
        # Buscamos reservas activas para el mismo lugar en la misma fecha
        reservas_coincidentes = ReservaEvento.objects.filter(
            lugar=self.lugar,
            fecha_reserva=self.fecha_reserva,
            estado_pago__in=['PENDIENTE', 'PAGADO'] # Filtra solo las reservas que sí ocupan espacio
        )

        # Si estamos editando una reserva existente, la excluimos de la búsqueda
        if self.pk:
            reservas_coincidentes = reservas_coincidentes.exclude(pk=self.pk)

        for r in reservas_coincidentes:
            # El evento actual inicia antes de que el otro termine (incluyendo su limpieza)
            # Y el evento actual termina (con su limpieza) después de que el otro inicia
            if self.hora_inicio < r.hora_fin_limpieza and self.hora_fin_limpieza > r.hora_inicio:
                raise ValidationError(
                    f"El horario seleccionado (incluyendo limpieza hasta las {self.hora_fin_limpieza.strftime('%H:%M')}) "
                    f"se cruza con el evento '{r.nombre_evento}' que está programado de "
                    f"{r.hora_inicio.strftime('%H:%M')} a {r.hora_fin_limpieza.strftime('%H:%M')}."
                )
                    
    def save(self, *args, **kwargs):
        if self.fecha_evento and self.hora_inicio and self.paquete:
            inicio_dt = dt_module.datetime.combine(self.fecha_evento, self.hora_inicio)
            
            if timezone.is_naive(inicio_dt):
                inicio_dt = timezone.make_aware(inicio_dt)
                
            duracion = self.paquete.duracion_horas
            self.hora_fin_limpieza = inicio_dt + dt_module.timedelta(hours=duracion + 5)
        
        super().save(*args, **kwargs)

    def calcular_total(self):
        total_productos = sum(rp.subtotal() for rp in self.productos.all())
        total_servicios = sum(rs.subtotal() for rs in self.servicios_extra.all())

        total_comida = 0
        if self.menu_comida:
            total_comida = self.menu_comida.precio_por_persona * self.asistentes

        total_acumulado = total_productos + total_servicios + total_comida

        if self.lugar:
            total_acumulado += self.lugar.precio_renta

        self.total = total_acumulado
    
        self.deposito_garantia = (self.total * Decimal('0.15')).quantize(Decimal('0.01'))
        self.save()

    def confirmar_y_despachar(self):
        """Cambia estado a Confirmado y resta stock real."""
        from django.db import transaction
        with transaction.atomic():
            if self.estado == 'Reservado':
                self.estado = 'Confirmado'
                self.save()
                
                for rp in self.productos.all():
                    if rp.producto.stock_disponible < rp.cantidad:
                        raise ValueError(f"No hay stock suficiente de {rp.producto.nombre_producto}")
                    
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=self,
                        tipo='SALIDA',
                        cantidad=rp.cantidad,
                        observacion=f"Salida por confirmación de Evento #{self.id}"
                    )
                    rp.producto.stock_disponible -= rp.cantidad
                    rp.producto.save()

    def finalizar_y_evaluar(self):
        """Cierra el evento y procesa el retorno de productos."""
        with transaction.atomic():
            evaluaciones = EvaluacionEvento.objects.filter(reserva=self)
            
            for rp in self.productos.all():
                evaluacion = evaluaciones.filter(producto=rp.producto).first()
                danados = evaluacion.cantidad_danada if evaluacion else 0
                buenos = rp.cantidad - danados

                if buenos > 0:
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=self,
                        tipo='ENTRADA',
                        cantidad=buenos,
                        observacion=f"Retorno post-evento #{self.id}"
                    )
                    rp.producto.stock_disponible += buenos

                if danados > 0:
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=self,
                        tipo='AJUSTE_DANO',
                        cantidad=danados,
                        observacion=f"Daño reportado: {evaluacion.observacion if evaluacion else 'Sin obs'}"
                    )
                
                rp.producto.save()
            
            self.estado = 'Finalizado'
            self.save()

    def finalizar_y_retornar_stock(self):
        """Procesa el re-ingreso de productos al inventario."""
        with transaction.atomic():
            evaluaciones = EvaluacionEvento.objects.filter(reserva=self)
        
            for rp in self.productos.all():
                evaluacion = evaluaciones.filter(producto=rp.producto).first()
                danados = evaluacion.cantidad_danada if evaluacion else 0
                buenos = rp.cantidad - danados

                if buenos > 0:
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=self,
                        tipo='ENTRADA',
                        cantidad=buenos,
                        observacion=f"Retorno sano de Evento #{self.id}"
                    )
                    rp.producto.stock_disponible += buenos

                if danados > 0:
                    MovimientoProducto.objects.create(
                        producto=rp.producto,
                        reserva=self,
                        tipo='AJUSTE_DANO',
                        cantidad=danados,
                        observacion=f"Pérdida/Daño en Evento #{self.id}"
                    )
            
                rp.producto.save()
        
            self.estado = 'Finalizado'
            self.save()

    def __str__(self):
        return f'Reserva {self.id} - {self.usuario.nombre}'


# ---------------- RESERVA PRODUCTO ----------------

class ReservaProducto(models.Model):
    reserva = models.ForeignKey(ReservaEvento, related_name='productos', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario_fijado = models.DecimalField(max_digits=10, decimal_places=2) # Precio al momento de reservar

    def subtotal(self):
        return self.cantidad * self.precio_unitario_fijado

# ---------------- RESERVA SERVICIO ----------------

class ReservaServicio(models.Model):

    reserva = models.ForeignKey(
        ReservaEvento,
        on_delete=models.CASCADE,
        related_name='servicios_extra'
    )
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, null=True, blank=True)

    cantidad = models.PositiveIntegerField(default=1)

    precio_fijado = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def subtotal(self):
        return self.cantidad * self.precio_fijado

    class Meta:
        unique_together = ('reserva', 'servicio')

    def __str__(self):
        if self.servicio:
            return f'Reserva #{self.reserva.id} - {self.servicio.nombre_servicio}'
        return f'Reserva #{self.reserva.id} - Servicio no especificado'

# ---------------- EVALUACION EVENTO ----------------

class EvaluacionEvento(models.Model):

    reserva = models.ForeignKey(ReservaEvento, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)

    cantidad_danada = models.IntegerField(default=0)

    costo_dano = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    observacion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    def __str__(self):
        return f'Evaluacion Reserva {self.reserva.id}'
    
# ---------------- PAGOS ----------------

class Pago(models.Model):
    METODO_PAGO_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Transferencia', 'Transferencia'),
        ('Tarjeta', 'Tarjeta'),
    ]

    TIPO_PAGO_CHOICES = [
        ('Anticipo', 'Anticipo'),
        ('Parcial', 'Parcial'),
        ('Final', 'Final'),
        ('Deposito', 'Deposito'),
        ('Reembolso', 'Reembolso'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    alquiler = models.ForeignKey(Alquiler, on_delete=models.CASCADE, null=True, blank=True)
    reserva = models.ForeignKey(ReservaEvento, on_delete=models.CASCADE, null=True, blank=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    tipo = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, default='Final')

    # =========================================================================
    # NUEVOS CAMPOS ADICIONALES PARA LA PASARELA PREMIUM (Permiten nulos)
    # =========================================================================
    # Campos para Transferencia
    transferencia_banco = models.CharField(max_length=50, null=True, blank=True)
    transferencia_tipo = models.CharField(max_length=20, null=True, blank=True)
    transferencia_numero = models.CharField(max_length=30, null=True, blank=True)

    # Campos para Tarjeta
    tarjeta_tipo = models.CharField(max_length=50, null=True, blank=True)
    tarjeta_titular = models.CharField(max_length=100, null=True, blank=True)
    # =========================================================================

    def __str__(self):
        return f'Pago {self.id} - {self.monto} ({self.metodo_pago})'
