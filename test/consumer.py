import requests

BASE_URL = "http://127.0.0.1:5000/patients"

# Crear un nuevo paciente
nuevo = {
    "first_name": "Juan",
    "last_name": "Pérez",
    "email": "juanp@example.com"
}
r = requests.post(BASE_URL, json=nuevo)
print("POST:", r.status_code, r.json())

# Obtener lista de pacientes
r = requests.get(BASE_URL)
print("GET:", r.status_code, r.json())

# Actualizar paciente
if r.json():
    patient_id = r.json()[0]['patient_id']
    r = requests.put(f"{BASE_URL}/{patient_id}", json={"phone": "5551112233"})
    print("PUT:", r.status_code, r.json())

# Eliminar paciente
if r.json():
    r = requests.delete(f"{BASE_URL}/{patient_id}")
    print("DELETE:", r.status_code)
