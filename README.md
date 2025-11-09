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

## Probar la interfaz web
1. Con Waitress sirviendo la aplicación (ver sección anterior), abre tu navegador en `http://localhost:5000/`.
2. Verifica que la tabla de pacientes carga los registros actuales y que puedes agregar un nuevo paciente con el formulario.
3. Comprueba que los selectores de citas se llenan automáticamente y crea una cita de prueba para confirmar que los cambios se reflejan en la tabla.
4. Asegúrate de que los mensajes de retroalimentación verde/rojo aparezcan tras cada acción para confirmar que la API respondió correctamente.
