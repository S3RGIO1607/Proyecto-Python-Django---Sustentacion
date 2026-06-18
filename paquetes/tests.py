from django.test import TestCase

# Create your tests here.

from decimal import Decimal
from django.urls import reverse
from .models import Paquete, PaqueteProducto, PaqueteServicio, Servicio
from inventario.models import Producto

class PaquetesTestCase(TestCase):

    def setUp(self):
        # 1. Simular sesión activa del administrador
        session = self.client.session
        session['usuario_id'] = 99
        session.save()

        # 2. Crear un producto base en el inventario para asociar a los paquetes
        self.producto = Producto.objects.create(
            nombre_producto="Mesa Tablón Rectangular",
            descripcion="Mesa de madera plegable para diez personas estable",
            precio_compra=80000,
            precio_alquiler=10000,
            stock_total=50,
            stock_disponible=50,
            estado='A'
        )

        # 3. Crear servicios base
        self.servicio_activo = Servicio.objects.create(
            nombre="Sonido Profesional Luces",
            descripcion="Montaje de dos cabinas de sonido con luces rítmicas LED",
            precio=150000,
            estado='A'
        )

        self.servicio_inactivo = Servicio.objects.create(
            nombre="Decoración Globos Vieja",
            descripcion="Decoraciones descontinuadas del catálogo por temporada",
            precio=40000,
            estado='I'
        )

        # 4. Crear un paquete maestro activo para consultas y ediciones
        self.paquete_activo = Paquete.objects.create(
            nombre="Paquete Cumpleaños Básico",
            descripcion="Combo ideal para celebraciones familiares e infantiles medianas",
            duracion_horas=5,
            precio=200000,
            deposito_garantia=Decimal('30000.00'), # 15% automático
            estado='A'
        )
        
        # Crear sus relaciones iniciales en el modelo intermedio
        PaqueteProducto.objects.create(paquete=self.paquete_activo, producto=self.producto, cantidad=5)
        PaqueteServicio.objects.create(paquete=self.paquete_activo, servicio=self.servicio_activo)


    # ==============================================================================
    # VISTAS: Catálogos y Listados
    # ==============================================================================
    def test_paquetes_catalogo_visible_publico(self):
        """Verificar que los clientes puedan ver los paquetes activos"""
        response = self.client.get(reverse('paquetes_catalogo'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.paquete_activo, response.context['paquetes'])

    def test_listar_paquetes_admin_separa_estados(self):
        """Verificar que el administrador vea listas separadas de activos e inactivos"""
        response = self.client.get(reverse('listar_paquetes'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.paquete_activo, response.context['paquetes'])


    # ==============================================================================
    # VISTA: registrar_paquete  
    # ==============================================================================
    def test_registrar_paquete_exitoso_calcula_valores(self):
        """Camino Feliz: Crear paquete, verificar cálculos automáticos de precio y depósito"""
        # Enviamos el formulario simulando los campos dinámicos y arreglos de IDs
        response = self.client.post(reverse('registrar_paquete'), {
            'txt_nombre': 'Paquete Empresarial Premium',
            'txt_descripcion': 'Montaje corporativo de alto impacto para juntas directivas',
            'txt_duracion_horas': '6',
            'productosIds': [self.producto.id],
            'serviciosIds': [self.servicio_activo.id],
            f'cantidades_prod_{self.producto.id}': '10' # 10 mesas * 10,000 = 100,000
        })
        # Verifica redirección exitosa
        self.assertEqual(response.status_code, 302)
        
        # Validar persistencia y cálculos matemáticos (100k de productos + 150k de servicio = 250k)
        nuevo_paquete = Paquete.objects.get(nombre='Paquete Empresarial Premium')
        self.assertEqual(nuevo_paquete.precio, 250000)
        self.assertEqual(nuevo_paquete.deposito_garantia, Decimal('37500.00')) # 15% de 250,000

    def test_registrar_paquete_fallo_sin_productos(self):
        """Validar rechazo si no se añade ningún producto al paquete"""
        response = self.client.post(reverse('registrar_paquete'), {
            'txt_nombre': 'Paquete Invalido Sin Nada',
            'txt_descripcion': 'Descripción operativa con longitud válida en caracteres',
            'txt_duracion_horas': '4',
            'productosIds': [], # Vacío
            'serviciosIds': [self.servicio_activo.id]
        })
        self.assertEqual(response.status_code, 200) # Recarga la misma plantilla para mostrar error
        self.assertIn("Debes seleccionar al menos un producto", response.context['error'])


    # ==============================================================================
    # VISTA: editar_paquete
    # ==============================================================================
    def test_editar_paquete_exitoso(self):
        """Camino Feliz: Modificar metadatos de un paquete existente"""
        response = self.client.post(reverse('editar_paquete', args=[self.paquete_activo.id]), {
            'txt_nombre': 'Nombre Totalmente Modificado',
            'txt_descripcion': 'Nueva descripción con la longitud requerida por el negocio',
            'txt_duracion_horas': '8',
            'productos_ids': [self.producto.id],
            'servicios_ids': [self.servicio_activo.id],
            f'cantidades_productos_{self.producto.id}': '2'
        })
        # Tu vista redirige al detalle tras guardar con éxito
        self.assertEqual(response.status_code, 302)
        self.paquete_activo.refresh_from_db()
        self.assertEqual(self.paquete_activo.nombre, 'Nombre Totalmente Modificado')


    # ==============================================================================
    # VISTAS: Control de Estados
    # ==============================================================================
    def test_eliminar_paquete(self):
        """Verificar que eliminar un paquete cambie su estado a 'I'"""
        response = self.client.get(reverse('eliminar_paquete', args=[self.paquete_activo.id]))
        self.assertEqual(response.status_code, 302)
        self.paquete_activo.refresh_from_db()
        self.assertEqual(self.paquete_activo.estado, 'I')


    # ==============================================================================
    # VISTAS: Gestión de Servicios Individuales
    # ==============================================================================
    def test_registrar_servicio_exitoso(self):
        """Camino Feliz: Registrar un servicio autónomo con datos limpios"""
        response = self.client.post(reverse('registrar_servicio'), {
            'txt_nombre': 'Decoración Premium Cristal',
            'txt_descripcion': 'Centros de mesa elegantes con bases de cristal templado',
            'txt_precio': '90000'
        })
        # Cambia 'gestionar_catalogos' si el name de tu URL es diferente
        self.assertEqual(response.status_code, 302) 
        self.assertTrue(Servicio.objects.filter(nombre='Decoración Premium Cristal').exists())

    def test_registrar_servicio_fallo_nombre_caracteres_especiales(self):
        """Validar que la regex rechace nombres de servicios con números o símbolos"""
        response = self.client.post(reverse('registrar_servicio'), {
            'txt_nombre': 'Servicio 123 @Fallas', # Inválido por la regex
            'txt_descripcion': 'Descripción operativa con longitud válida en caracteres',
            'txt_precio': '50000'
        })
        self.assertEqual(response.status_code, 200) # Retorna el formulario limpio con el error
        # Buscamos en los mensajes de Django almacenados en la request
        mensajes = [m.message for m in response.context['messages']]
        self.assertTrue(any("alfabético" in m for m in mensajes))

    def test_editar_servicio_exitoso(self):
        """Camino Feliz: Actualizar costo y metadatos de un servicio"""
        response = self.client.post(reverse('editar_servicio'), {
            'txt_id': self.servicio_activo.id,
            'txt_nombre': 'Sonido Actualizado',
            'txt_descripcion': 'Nueva descripción del montaje de sonido para eventos corporativos',
            'txt_precio': '180000',
            'txt_estado': 'A'
        })
        self.assertEqual(response.status_code, 302)
        self.servicio_activo.refresh_from_db()
        self.assertEqual(self.servicio_activo.precio, 180000)

    def test_eliminar_servicio(self):
        """Verificar que se inactive el servicio pasándolo a 'I'"""
        response = self.client.get(reverse('eliminar_servicio', args=[self.servicio_activo.id]))
        self.assertEqual(response.status_code, 302)
        self.servicio_activo.refresh_from_db()
        self.assertEqual(self.servicio_activo.estado, 'I')