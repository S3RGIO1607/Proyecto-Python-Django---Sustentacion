from django.db import models
from decimal import Decimal
from inventario.models import Producto

# Create your models here.

# ---------------- SERVICIOS ----------------

class Servicio(models.Model):

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    nombre_servicio = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio_servicio = models.DecimalField(max_digits=10, decimal_places=2)

    nombre_empresa_externa = models.CharField(max_length=100, default="Independiente", verbose_name="Empresa Proveedora")
    nombre_proveedor = models.CharField(max_length=100, default="Por Asignar", verbose_name="Nombre del Especialista / Contacto")
    telefono_proveedor = models.CharField(max_length=15, default="0000000000", verbose_name="Teléfono de Contacto")
    nit_o_cedula_proveedor = models.CharField(max_length=20, default="000000000", verbose_name="NIT o Cédula")

    costo_proveedor = models.IntegerField(default=0, verbose_name="Lo que cobra el externo a Arron")

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )

    def __str__(self):
        return f"{self.nombre_servicio} ({self.nombre_empresa_externa})"


# ---------------- PAQUETES ----------------

class Paquete(models.Model):

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    nombre = models.CharField(max_length=255)
    descripcion = models.TextField()

    precio = models.DecimalField(max_digits=10, decimal_places=2)

    deposito_garantia = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    duracion_horas = models.PositiveIntegerField()
    capacidad_base = models.PositiveIntegerField(default=100)

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )

    def calcular_precio(self):

        total = Decimal('0.00')

        for pp in self.paqueteproducto_set.all():
            total += pp.producto.precio_alquiler * pp.cantidad

        for ps in self.paqueteservicio_set.all():
            total += ps.servicio.precio_servicio

        self.precio = total

        # 🔥 DEPÓSITO AUTOMÁTICO
        self.deposito_garantia = (total * Decimal('0.15')).quantize(Decimal('0.01'))

        self.save()

    def __str__(self):
        return self.nombre


# ---------------- PAQUETE PRODUCTO ----------------

class PaqueteProducto(models.Model):

    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)

    cantidad = models.PositiveIntegerField()

    class Meta:
        unique_together = ('paquete', 'producto')

    def __str__(self):
        return f'{self.paquete.nombre} - {self.producto.nombre_producto}'


# ---------------- PAQUETE SERVICIO ----------------

class PaqueteServicio(models.Model):

    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('paquete', 'servicio')

    def __str__(self):
        return f'{self.paquete.nombre} - {self.servicio.nombre_servicio}'
    
