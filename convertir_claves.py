import os
import django

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arrons.settings') # Cambia 'tu_proyecto' por el nombre de tu carpeta principal
django.setup()

from django.contrib.auth.hashers import make_password, identify_hasher
from usuarios.models import Usuario 

def migrar_contrasenas():
    usuarios = Usuario.objects.all()
    convertidos = 0

    for u in usuarios:
        try:
            # identify_hasher intenta ver si la clave ya está encriptada
            identify_hasher(u.contrasena)
            print(f"[-] Usuario {u.nombre} ya tiene clave encriptada. Saltando...")
        except ValueError:
            # Si lanza ValueError, es porque la clave es texto plano
            u.contrasena = make_password(u.contrasena)
            u.save()
            convertidos += 1
            print(f"[+] Usuario {u.nombre} actualizado con éxito.")

    print(f"\n--- Proceso terminado. Se actualizaron {convertidos} usuarios. ---")

if __name__ == "__main__":
    migrar_contrasenas()