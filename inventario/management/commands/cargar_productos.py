import os
import pandas as pd
from django.core.management.base import BaseCommand
from inventario.models import Producto
from django.core.files import File

class Command(BaseCommand):
    help = 'Carga masiva: Solo crea registros nuevos, ignora duplicados existentes.'

    def handle(self, *args, **options):
        ruta_csv = 'data_productos_arrons'
        ruta_fotos = 'fotos_ipercarga'
        extensiones_validas = ['.jpg', '.png', '.jpeg', '.JPG', '.PNG', '.JPEG']

        if not os.path.exists(ruta_csv):
            self.stdout.write(self.style.ERROR(f'❌ No se encuentra la carpeta: {ruta_csv}'))
            return

        archivos_csv = [f for f in os.listdir(ruta_csv) if f.endswith('.csv')]

        creados = 0
        omitidos = 0

        for archivo in archivos_csv:
            self.stdout.write(self.style.SUCCESS(f'📖 Leyendo: {archivo}'))
            df = pd.read_csv(os.path.join(ruta_csv, archivo))
            
            for _, f in df.iterrows():
                # --- VALIDACIÓN ESTRICTA ---
                # get_or_create: Si el nombre ya existe, no hace NADA con el registro.
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
                    status_msg = self.style.SUCCESS(f"✅ NUEVO: {f['nombre']}")
                    
                    # --- SOLO CARGAMOS IMAGEN SI ES NUEVO ---
                    nombre_base = os.path.splitext(str(f['imagen']))[0].strip()
                    archivo_encontrado = None
                    nombre_archivo_final = None

                    for ext in extensiones_validas:
                        posible_ruta = os.path.join(ruta_fotos, nombre_base + ext)
                        if os.path.exists(posible_ruta):
                            archivo_encontrado = posible_ruta
                            nombre_archivo_final = nombre_base + ext
                            break

                    if archivo_encontrado:
                        with open(archivo_encontrado, 'rb') as doc:
                            obj.imagen.save(nombre_archivo_final, File(doc), save=True)
                        self.stdout.write(f"{status_msg} + 📸 Foto cargada")
                    else:
                        self.stdout.write(f"{status_msg} + ⚠️ Sin foto")
                
                else:
                    omitidos += 1
                    # No hacemos nada, solo informamos que se saltó
                    self.stdout.write(self.style.WARNING(f"🚫 OMITIDO (Ya existe): {f['nombre']}"))

        # Reporte final de seguridad
        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS(f"🚀 PROCESO FINALIZADO"))
        self.stdout.write(f"📦 Productos nuevos agregados: {creados}")
        self.stdout.write(f"🛡️  Duplicados protegidos (no tocados): {omitidos}")
        self.stdout.write("="*40)