from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Producto



class InventarioTestCase(TestCase):

    def setUp(self):
        """Configuración inicial para las pruebas de inventario"""
        # 1. Crear una sesión de usuario simulada (Requerida por el middleware/vistas)
        session = self.client.session
        session['usuario_id'] = 99  # ID ficticio de usuario administrador
        session['nombre_usuario'] = 'Sergio Admin'
        session.save()

        # 2. Crear una imagen falsa en memoria para pasar la validación obligatoria
        self.imagen_prueba = SimpleUploadedFile(
            name='test_image.png',
            content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...', # Bytes simulados de un PNG
            content_type='image/png'
        )

        # 3. Crear productos base para las pruebas de listado, edición y filtros
        self.producto_activo = Producto.objects.create(
            nombre_producto="Silla Rimax Blanca",
            descripcion="Silla plástica sin brazos ideal para eventos corporativos",
            precio_compra=15000,
            precio_alquiler=2500,
            stock_total=100,
            stock_disponible=80,
            estado='A',
            imagen=self.imagen_prueba
        )

        self.producto_bajo_stock = Producto.objects.create(
            nombre_producto="Videobeam Epson 4K",
            descripcion="Proyector de alta gama para presentaciones empresariales",
            precio_compra=1500000,
            precio_alquiler=120000,
            stock_total=3,
            stock_disponible=2,  # Al ser menor a 5, activará las alertas de bajo stock
            estado='A',
            imagen=self.imagen_prueba
        )

        self.producto_inactivo = Producto.objects.create(
            nombre_producto="Manteles Sucios Viejos",
            descripcion="Mantelería descontinuada por manchas severas irreparables",
            precio_compra=8000,
            precio_alquiler=500,
            stock_total=10,
            stock_disponible=0,
            estado='I',  # Inactivo
            imagen=self.imagen_prueba
        )

    # ==============================================================================
    # VISTA: exportar_productos_pdf
    # ==============================================================================
    def test_exportar_productos_pdf_retorna_archivo_correcto(self):
        """Verificar la generación exitosa del PDF gerencial con su content-type"""
        response = self.client.get(reverse('exportar_productos_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_exportar_productos_pdf_filtro_stock_bajo(self):
        """Verificar que el parámetro bajo_stock filtre los productos en el PDF"""
        response = self.client.get(reverse('exportar_productos_pdf'), {'bajo_stock': 'on'})
        self.assertEqual(response.status_code, 200)
        # Revisamos si en el contexto del PDF solo se procesó el producto con stock < 5
        productos_reporte = response.context['productos']
        self.assertEqual(len(productos_reporte), 1)
        self.assertEqual(productos_reporte[0].nombre_producto, "Videobeam Epson 4K")

    # ==============================================================================
    # VISTA: listar_productos
    # ==============================================================================
    def test_listar_productos_separa_activos_e_inactivos(self):
        """Garantizar que la vista divida el inventario según su estado (A / I)"""
        response = self.client.get(reverse('listar_productos'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.producto_activo, response.context['productos'])
        self.assertIn(self.producto_inactivo, response.context['productos_inactivos'])


    # ==============================================================================
    # VISTA: mostrar_registro_producto
    # ==============================================================================
    def test_mostrar_registro_producto_renderiza_formulario(self):
        """Verificar acceso a la interfaz limpia de registro"""
        response = self.client.get(reverse('mostrar_registro_producto'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'producto/crear.html')


    # ==============================================================================
    # VISTA: registrar_producto
    # ==============================================================================
    def test_registrar_producto_exitoso(self):
        """Camino Feliz: Registrar un nuevo elemento en el inventario con datos válidos"""
        response = self.client.post(reverse('registrar_producto'), {
            'txt_nombre': 'Carpa Elegante 6x6',
            'txt_descripcion': 'Carpa estructural impermeable con paredes panorámicas para eventos exteriores',
            'txt_precio_compra': '450000',
            'txt_precio_alquiler': '80000',
            'txt_stock_total': '5',
            'txt_imagen': self.imagen_prueba
        })
        self.assertEqual(response.status_code, 302)  # Redirige a la lista
        self.assertTrue(Producto.objects.filter(nombre_producto='Carpa Elegante 6x6').exists())

    def test_registrar_producto_fallo_descripcion_corta(self):
        """Validar el rechazo si la descripción tiene menos de 25 caracteres"""
        response = self.client.post(reverse('registrar_producto'), {
            'txt_nombre': 'Carpa Corta',
            'txt_descripcion': 'Muy corta',  # Incumple el rango (25-350)
            'txt_precio_compra': '10000',
            'txt_precio_alquiler': '2000',
            'txt_stock_total': '5',
            'txt_imagen': self.imagen_prueba
        })
        self.assertEqual(response.status_code, 302)
        # Comprobar que redirige de vuelta al formulario por el fallo
        self.assertRedirects(response, reverse('mostrar_registro_producto'))


    # ==============================================================================
    # VISTA: mostrar_detalle_producto
    # ==============================================================================
    def test_mostrar_detalle_producto_carga_objeto(self):
        """Verificar la consulta individual de un producto específico"""
        response = self.client.get(reverse('mostrar_detalle_producto', args=[self.producto_activo.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['producto'], self.producto_activo)


    # ==============================================================================
    # VISTA: pre_editar_producto
    # ==============================================================================
    def test_pre_editar_producto_carga_interfaz(self):
        """Verificar que traiga los datos actuales del producto al formulario de edición"""
        response = self.client.get(reverse('pre_editar_producto', args=[self.producto_activo.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'producto/editar.html')


    # ==============================================================================
    # VISTA: editar_producto
    # ==============================================================================
    def test_editar_producto_exitoso(self):
        """Camino Feliz: Modificar atributos respetando las reglas de negocio"""
        response = self.client.post(reverse('editar_producto'), {
            'txt_id': self.producto_activo.id,
            'txt_nombre': 'Silla Rimax Modificada',
            'txt_descripcion': 'Silla plástica sin brazos ideal para eventos corporativos y fiestas',
            'txt_precio_compra': '16000',
            'txt_precio_alquiler': '3000',
            'txt_estado': 'A',
            'txt_stock_total': '100',
            'txt_stock_disponible': '95',  # Lógica válida: disponible <= total
        })
        self.assertEqual(response.status_code, 302)
        self.producto_activo.refresh_from_db()
        self.assertEqual(self.producto_activo.nombre_producto, 'Silla Rimax Modificada')

    def test_editar_producto_fallo_stock_incoherente(self):
        """Validar restricción: stock disponible NO puede superar al total"""
        response = self.client.post(reverse('editar_producto'), {
            'txt_id': self.producto_activo.id,
            'txt_nombre': 'Silla Rimax Error',
            'txt_descripcion': 'Silla plástica sin brazos ideal para eventos corporativos y fiestas',
            'txt_precio_compra': '16000',
            'txt_precio_alquiler': '3000',
            'txt_estado': 'A',
            'txt_stock_total': '50',
            'txt_stock_disponible': '60',  # ERROR: 60 > 50
        })
        self.assertEqual(response.status_code, 302)
        # Validar que en la base de datos NO se guardó el cambio absurdo
        self.producto_activo.refresh_from_db()
        self.assertNotEqual(self.producto_activo.stock_total, 50)


    # ==============================================================================
    # VISTA: eliminar_producto
    # ==============================================================================
    def test_eliminar_producto_borrado_logico(self):
        """Verificar que dar de baja cambie el estado a 'I' sin remover el registro"""
        response = self.client.get(reverse('eliminar_producto', args=[self.producto_activo.id]))
        self.assertEqual(response.status_code, 302)
        self.producto_activo.refresh_from_db()
        self.assertEqual(self.producto_activo.estado, 'I')


    # ==============================================================================
    # VISTA: habilitar_producto
    # ==============================================================================
    def test_habilitar_producto_reactiva_estado(self):
        """Verificar que un producto descontinuado pueda volver a marcarse activo ('A')"""
        # CORREGIDO: Se cambió 'producto_inactivos' por 'producto_inactivo' (en singular)
        response = self.client.get(reverse('habilitar_producto', args=[self.producto_inactivo.id]))
        self.assertEqual(response.status_code, 302)
        self.producto_inactivo.refresh_from_db()
        self.assertEqual(self.producto_inactivo.estado, 'A')


    # ==============================================================================
    # VISTA: listar_movimientos
    # ==============================================================================
    def test_listar_movimientos_historico(self):
        """Garantizar el acceso al log transaccional de movimientos de kardex"""
        response = self.client.get(reverse('movimientos_producto'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'producto/movimientos.html')

    # ==============================================================================
    # VISTA: productos_catalogo
    # ==============================================================================
    def test_productos_catalogo_visible_para_clientes(self):
        """Verificar que el catálogo público liste productos activos con existencias"""
        response = self.client.get(reverse('productos_catalogo'))
        self.assertEqual(response.status_code, 200)
        # El producto activo debe verse, el inactivo o con stock 0 no debe listarse
        self.assertIn(self.producto_activo, response.context['productos'])