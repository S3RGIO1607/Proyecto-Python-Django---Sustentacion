from django.test import TestCase
from django.urls import reverse
from .models import Usuario, Rol
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password



class UsuarioTestCase(TestCase):

    def setUp(self):
        """Preparación de los Roles y Usuarios base requeridos para los flujos"""
        # 1. Crear los roles necesarios en la BD de pruebas para evitar errores de llave foránea
        self.rol_admin = Rol.objects.create(id=1, nombre="Administrador")
        self.rol_organizador = Rol.objects.create(id=2, nombre="Organizador")
        self.rol_bodega = Rol.objects.create(id=3, nombre="Supervisor Bodega")
        self.rol_cliente = Rol.objects.create(id=4, nombre="Cliente")

        # 2. Tu usuario base de pruebas (Hasheamos la clave porque iniciar_sesion usa check_password)
        self.usuario = Usuario.objects.create(
            numero_documento="123456789",
            nombre='Test User',
            correo='testuser@example.com',
            contrasena=make_password('Password123.'),
            direccion='123 Test Street',
            telefono='1234567890',
            nivel_educativo='Profesional',
            referencia_personal='Test Reference',
            telefono_referencia_personal='0987654321',
            eps='Test EPS',
            estado='A',
            rol_id=1
        )

        # 3. Usuario inactivo para validar bloqueos de seguridad en el login
        self.cliente_inactivo = Usuario.objects.create(
            numero_documento="87654321",
            nombre="Cliente Inactivo",
            correo="inactivo@gmail.com",
            contrasena=make_password("Cliente123*"),
            direccion="456 Inactive Street",
            telefono="9876543210",
            estado="I",
            rol_id=4
        )

    def test_home(self):
        """Verificar que el home cargue correctamente la plantilla index.html"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_nosotros(self):
        """Verificar que la vista de nosotros cargue correctamente la plantilla nosotros.html"""
        response = self.client.get(reverse('nosotros'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'nosotros.html')

    def test_iniciar_sesion_exitoso_admin(self):
        """Verificar ingreso de admin con credenciales válidas y redirección a su panel"""
        response = self.client.post(reverse('iniciar_sesion'), {
            'numero_documento': '123456789',
            'contrasena': 'Password123.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard_admin'))
        # Comprobar que las variables quedaron en la sesión HTTP
        self.assertEqual(self.client.session.get('usuario_id'), self.usuario.id)
        self.assertEqual(self.client.session.get('rol'), 1)

    def test_iniciar_sesion_fallido_contrasena_erronea(self):
        """Verificar rechazo del sistema si la clave no coincide"""
        response = self.client.post(reverse('iniciar_sesion'), {
            'numero_documento': '123456789',
            'contrasena': 'ClaveIncorrecta999'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Documento o contraseña incorrectos", response.context['error'])

    def test_iniciar_sesion_bloqueo_usuario_inactivo(self):
        """Verificar que un usuario con estado 'I' no pueda acceder"""
        response = self.client.post(reverse('iniciar_sesion'), {
            'numero_documento': '87654321',
            'contrasena': 'Cliente123*'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Este usuario está inactivo", response.context['error'])

    def test_cerrar_sesion_limpia_variables(self):
        """Verificar que el logout vacíe el diccionario de la sesión"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('usuario_id', self.client.session)

    def test_cambiar_clave_exitoso(self):
        """Camino Feliz: Verificar que el usuario pueda cambiar su contraseña correctamente"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        # Ajustamos temporalmente a texto plano para que el operador != de la view no falle
        self.usuario.contrasena = 'Password123.'
        self.usuario.save()

        response = self.client.post(reverse('cambiar_clave'), {
            'clave_actual': 'Password123.',
            'nueva_clave': 'NuevaClave123*',
            'confirmar_clave': 'NuevaClave123*'
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('mi_perfil'))

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.contrasena, 'NuevaClave123*')

    def test_cambiar_clave_fallido_no_coinciden(self):
        """Verificar que si las nuevas contraseñas no coinciden, no se cambie nada"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.post(reverse('cambiar_clave'), {
            'clave_actual': 'Password123.',
            'nueva_clave': 'NuevaClave123*',
            'confirmar_clave': 'ClaveDiferente456*'
        })

        self.assertEqual(response.status_code, 200)
        
        self.usuario.refresh_from_db()
        self.assertTrue(check_password('Password123.', self.usuario.contrasena))

    def test_dashboard_admin_anonimo_redirige_a_login(self):
        """Si no hay sesión iniciada, debe patear al login"""
        response = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('iniciar_sesion'))

    def test_dashboard_admin_exitoso_con_sesion(self):
        """Verificar que el admin logueado acceda al panel y reciba las métricas"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard_admin.html')
        self.assertIn('total_pagos_mes', response.context)
        self.assertIn('actividades', response.context)

    def test_dashboard_bodega_anonimo_redirige(self):
        """Si no hay sesión, bodega debe rebotar al login"""
        response = self.client.get(reverse('dashboard_bodega'))
        self.assertRedirects(response, reverse('iniciar_sesion'))

    def test_dashboard_bodega_exitoso_con_sesion(self):
        """Verificar acceso al panel de bodega y paso de alertas de stock"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.get(reverse('dashboard_bodega'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard_bodega.html')
        self.assertIn('productos_alerta', response.context)

    def test_dashboard_organizador_exitoso_con_sesion(self):
        """Verificar acceso a la agenda del organizador de eventos con sesión activa"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.get(reverse('dashboard_organizador'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard_organizador.html')
        self.assertIn('eventos_semana', response.context)

    def test_mi_perfil_cambio_dinamico_de_plantilla_admin(self):
        """Verificar que un admin (rol != 4) use base2.html en su perfil"""
        session = self.client.session
        session['usuario_id'] = self.usuario.id
        session.save()

        response = self.client.get(reverse('mi_perfil'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['base_to_extend'], 'base2.html')

    def test_listar_usuarios_separa_activos_e_inactivos(self):
        """Verificar el renderizado de listas de usuarios activos e inactivos"""
        response = self.client.get(reverse('listar_usuarios'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.usuario, response.context['usuarios'])
        self.assertIn(self.cliente_inactivo, response.context['usuarios_inactivos'])

    def test_mostrar_detalle_usuario(self):
        """Verificar que cargue la vista de consulta de un usuario específico"""
        response = self.client.get(reverse('mostrar_detalle_usuario', args=[self.usuario.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['usuario'], self.usuario)

    def test_mostrar_registro_usuario_carga_formulario(self):
        """Verificar que cargue el formulario HTML para la creación de usuarios"""
        response = self.client.get(reverse('mostrar_registro_usuario'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('roles', response.context)

    def test_registrar_usuario(self):
        """Test de registro exitoso adaptado a los parámetros del backend"""
        response = self.client.post(reverse('registrar_usuario'), {
            'txt_numero_documento': '987654321',
            'txt_nombre': 'New User',
            'txt_correo': 'newuser@example.com',
            'txt_contrasena': 'Password123.',
            'txt_direccion': '456 New Street',
            'txt_telefono': '0987654321',
            'txt_nivel_educativo': 'Profesional',
            'txt_referencia_personal': 'New Reference',
            'txt_telefono_referencia_personal': '1234567890',
            'txt_eps': 'New EPS',
            'txt_estado': 'A',
            'txt_rol': 1
        })
        self.assertEqual(Usuario.objects.count(), 3)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_usuarios'))

    def test_registrar_usuario_fallo_contrasena_debil(self):
        """Validar rechazo si la contraseña no cumple la expresión regular (sin símbolos)"""
        response = self.client.post(reverse('registrar_usuario'), {
            'txt_numero_documento': '111111111',
            'txt_nombre': 'Usuario Invalido',
            'txt_correo': 'invalido@arron.com',
            'txt_contrasena': 'debileson',
            'txt_rol': 2
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("La contraseña no cumple con los requisitos", response.context['error'])

    def test_pre_editar_usuario_carga_formulario(self):
        """Verificar la carga de la interfaz de edición con los datos del usuario"""
        response = self.client.get(reverse('pre_editar_usuario', args=[self.usuario.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['usuario'], self.usuario)

    def test_editar_usuario_guarda_cambios_via_post(self):
        """Verificar que la petición POST actualice los datos del usuario en la BD"""
        response = self.client.post(reverse('editar_usuario'), {
            'txt_id': self.usuario.id,
            'txt_numero_documento': '123456789',
            'txt_nombre': 'Test User Modificado',
            'txt_correo': 'testuser_mod@example.com',
            'txt_contrasena': self.usuario.contrasena,
            'txt_direccion': 'Nueva Direccion 456',
            'txt_telefono': '3333333333',
            'txt_nivel_educativo': 'Postgrado',
            'txt_referencia_personal': 'Reference Mod',
            'txt_telefono_referencia_personal': '0987654321',
            'txt_eps': 'Sura',
            'txt_estado': 'A',
            'txt_rol': 1
        })
        self.assertRedirects(response, reverse('listar_usuarios'))
        
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nombre, 'Test User Modificado')
        self.assertEqual(self.usuario.direccion, 'Nueva Direccion 456')

    def test_eliminar_usuario_cambia_estado_a_inactivo(self):
        """La acción de eliminar altera el estado a 'I' (Borrado lógico)"""
        response = self.client.get(reverse('eliminar_usuario', args=[self.usuario.id]))
        self.assertEqual(response.status_code, 302)
        
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.estado, "I")

    def test_usuarios_habilitar_revierte_a_activo(self):
        """Verificar que la acción de habilitar pase el estado de 'I' a 'A'"""
        # Partimos del cliente inactivo configurado en el setUp
        response = self.client.get(reverse('usuarios_habilitar', args=[self.cliente_inactivo.id]))
        self.assertRedirects(response, reverse('listar_usuarios'))
        
        self.cliente_inactivo.refresh_from_db()
        self.assertEqual(self.cliente_inactivo.estado, 'A')
        

    def test_registro_cliente_exitoso(self):
        """Verificar el formulario de auto-registro para los Clientes externos"""
        response = self.client.post(reverse('registro'), {
            'numero_documento': '555555555',
            'nombre': 'Cliente Nuevo',
            'correo': 'cliente_nuevo@gmail.com',
            'contrasena': 'Cliente123*',
            'direccion': 'Calle Falsa 123',
            'telefono': '3124567890'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('iniciar_sesion'))
        
        cliente_creado = Usuario.objects.get(numero_documento='555555555')
        self.assertEqual(cliente_creado.rol.id, 4)