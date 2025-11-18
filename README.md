# OMAS

## Ejecutar backend y frontend con Waitress
1. Opcionalmente crea y activa un entorno virtual de Python 3.10+.
2. Instala las dependencias del proyecto (incluye Waitress para servir la app en producción ligera):
   ```bash
   pip install -r test/requirements.txt.txt waitress
   ```
3. Define la variable de entorno `DATABASE_URL` si necesitas apuntar a una base de datos distinta; por defecto se usa `mysql+pymysql://root:123456@localhost:3306/omasdb`.
4. Inicia la aplicación completa con Waitress para obtener un servidor WSGI más robusto que el integrado de Flask:
   ```bash
   waitress-serve --listen=0.0.0.0:5000 test.main:app
   ```
5. Abre tu navegador y visita `http://localhost:5000/` para cargar la interfaz web.
6. Usa la interfaz para listar, crear y eliminar pacientes o programar citas; todas las acciones utilizan la API Flask en segundo plano sobre el mismo dominio `localhost:5000`.

> **Tip:** La ruta `http://localhost:5000/api` devuelve un JSON con la lista de recursos expuestos por el backend si necesitas una verificación rápida del API.

## Autenticación demo y casos de uso cubiertos
- Todas las operaciones que modifican datos (pacientes, horarios y citas) requieren un token de sesión. Inicia sesión desde la tarjeta "Acceso seguro" ingresando el tipo de usuario (paciente o proveedor), el correo registrado en la base de datos y el NIP configurado.
- Define el NIP mediante la variable `DEMO_LOGIN_PIN` (por defecto `4321`). Cambia este valor si compartirás la demo públicamente.
- Tras iniciar sesión el frontend almacena el token en `localStorage` y lo adjunta en la cabecera `X-Session-Token` para cada petición POST/PUT/DELETE.
- Los cinco casos de uso prioritarios del SRS disponibles en la interfaz son:
  1. **F1-F2**: Inicio/cierre de sesión de pacientes o proveedores para proteger la información clínica.
  2. **U1**: Alta y consulta de pacientes desde el panel con validación de campos.
  3. **U5**: Definición y limpieza de disponibilidad semanal de proveedores sin traslapes.
  4. **U1-U4**: Reserva de citas de 30 minutos basada en disponibilidad real, con verificación automática de conflictos.
  5. **U3**: Cancelación segura de citas confirmadas, manteniendo bitácora del cambio de estado.

## Probar la interfaz web
1. Con Waitress sirviendo la aplicación (ver sección anterior), abre tu navegador en `http://localhost:5000/`.
2. Inicia sesión con un correo real de paciente o proveedor y el NIP configurado; verifica que el resumen muestre la expiración del token.
3. Comprueba que la tabla de pacientes carga los registros actuales y que puedes agregar un nuevo paciente con el formulario autenticado.
4. Configura uno o más horarios en la tarjeta de disponibilidad y verifica que aparezcan en la tabla y en el widget de consulta de horarios rápidos.
5. Usa los selectores de citas para agendar una cita de prueba; asegúrate de que se respeten los 30 minutos y que los choques muestren un mensaje claro.
6. Cancela una cita existente desde el botón de la tabla y verifica que el estado cambie a `canceled`.
7. Trata de eliminar un paciente con una cita en estado `booked` y confirma que la API impide la operación y emite un mensaje explicativo.
