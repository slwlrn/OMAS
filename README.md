# OMAS

## Ejecutar la API (backend)
1. Opcionalmente crea y activa un entorno virtual de Python 3.10+.
2. Instala las dependencias del proyecto (incluye Waitress para servir la app en producción ligera):
   ```bash
   pip install -r test/requirements.txt.txt waitress
   ```
3. Define la variable de entorno `DATABASE_URL` si necesitas apuntar a una base de datos distinta; por defecto se usa `mysql+pymysql://root:123456@localhost:3306/omasdb`.
4. Inicia la API usando Waitress para obtener un servidor WSGI más robusto que el integrado de Flask:
   ```bash
   waitress-serve --listen=0.0.0.0:5000 test.main:app
   ```

## Ejecutar el frontend
1. Asegúrate de que la API esté corriendo en `http://localhost:5000`.
2. Desde la carpeta `test/`, levanta un servidor estático simple (por ejemplo, con Python):
   ```bash
   cd test
   python -m http.server 8000
   ```
3. Abre tu navegador y visita `http://localhost:8000/frontend.html` para cargar la interfaz.
4. Usa la interfaz para listar, crear y eliminar pacientes o programar citas; todas las acciones utilizan la API Flask en segundo plano.

## Probar la API manualmente
1. Con la API en marcha, abre otra terminal en la raíz del repositorio.
2. Ejecuta el cliente de ejemplo que realiza operaciones CRUD básicas sobre `/patients`:
   ```bash
   python test/consumer.py
   ```
3. Verifica en la terminal las respuestas HTTP para confirmar que los endpoints funcionan correctamente.
