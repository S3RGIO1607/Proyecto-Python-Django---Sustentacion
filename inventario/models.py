from django.db import models

# Create your models here.
class Producto(models.Model):

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    nombre_producto = models.CharField(max_length=255)
    descripcion = models.TextField()

    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_alquiler = models.DecimalField(max_digits=10, decimal_places=2)

    stock_total = models.IntegerField(default=0)
    stock_disponible = models.IntegerField(default=0)

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )

    imagen = models.ImageField(upload_to='Producto/Imagenes/', null=True, blank=True)

    def __str__(self):
        return self.nombre_producto

class MovimientoProducto(models.Model):

    TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('AJUSTE_DANO', 'Ajuste Daño'),
        ('COMPRA', 'Compra'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)

    alquiler = models.ForeignKey(
        'operaciones.Alquiler',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    reserva = models.ForeignKey(
        'operaciones.ReservaEvento',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_MOVIMIENTO_CHOICES
    )

    cantidad = models.IntegerField()

    fecha = models.DateTimeField(auto_now_add=True)

    observacion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.tipo} - {self.producto.nombre_producto}'