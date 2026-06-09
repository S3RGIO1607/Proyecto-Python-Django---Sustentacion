from django.db import models
# Create your models here

# ---------------- ROLES ----------------

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return self.nombre


# ---------------- USUARIOS ----------------

class Usuario(models.Model):

    NIVEL_EDUCATIVO_CHOICES = [
        ('Bachiller', 'Bachiller'),
        ('Tecnico', 'Tecnico'),
        ('Tecnologo', 'Tecnologo'),
        ('Profesional', 'Profesional'),
    ]

    ESTADO_CHOICES = [
        ('A', 'Activo'),
        ('I', 'Inactivo'),
    ]

    numero_documento = models.BigIntegerField(unique=True)
    nombre = models.CharField(max_length=255)
    correo = models.EmailField(unique=True)
    contrasena = models.CharField(max_length=255)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)

    nivel_educativo = models.CharField(
        max_length=20,
        choices=NIVEL_EDUCATIVO_CHOICES,
        null=True,
        blank=True
    )

    referencia_personal = models.CharField(max_length=255, null=True, blank=True)
    telefono_referencia_personal = models.CharField(max_length=20, null=True, blank=True)
    eps = models.CharField(max_length=255, null=True, blank=True)

    estado = models.CharField(
        max_length=1,
        choices=ESTADO_CHOICES,
        default='A'
    )

    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre