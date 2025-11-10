// URL base de la API Flask
const API_BASE = window.location.origin;

// Elementos del DOM reutilizables
const feedbackEl = document.getElementById("feedback");
const patientsTableBody = document.querySelector("#patients-table tbody");
const appointmentsTableBody = document.querySelector("#appointments-table tbody");
const appointmentForm = document.getElementById("appointment-form");
const appointmentPatientSelect = document.getElementById("appointment-patient");
const appointmentProviderSelect = document.getElementById("appointment-provider");
const clearProviderSelectionButton = document.getElementById(
  "clear-provider-selection"
);
const appointmentDateInput = document.getElementById("appointment-date");
const appointmentStartTimeInput = document.getElementById("appointment-start-time");
const appointmentStartInput = document.getElementById("appointment-start");
const appointmentEndInput = document.getElementById("appointment-end");
const appointmentTimeSummary = document.getElementById("appointment-time-summary");
const providerAvailabilityWrapper = document.getElementById(
  "provider-availability-wrapper"
);
const providerAvailabilityProviderName = document.getElementById(
  "provider-availability-provider-name"
);
const providerAvailabilityContent = document.getElementById(
  "provider-availability-content"
);
const DEFAULT_APPOINTMENT_DURATION_MINUTES = 30;
const WEEKDAY_NAMES = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

/**
 * Muestra mensajes de estado globales en la página (éxito o error).
 * Se usa tanto para respuestas positivas como negativas.
 */
function showFeedback(message, type = "success") {
  feedbackEl.textContent = message;
  feedbackEl.className = `alert alert-${type}`;
  feedbackEl.classList.remove("d-none");
  setTimeout(() => feedbackEl.classList.add("d-none"), 4000);
}

/**
 * Helper para capturar errores fetch y lanzar alertas visibles.
 */
async function handleResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok) {
    let message = `Error ${response.status}`;

    if (contentType.includes("application/json")) {
      try {
        const data = await response.json();
        message = data.error || JSON.stringify(data);
      } catch (err) {
        message = `Error ${response.status}`;
      }
    } else {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }

    showFeedback(message, "danger");
    alert(message);
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  if (contentType.includes("application/json")) {
    return response.json();
  }

  if (contentType.startsWith("text/")) {
    return response.text();
  }

  return null;
}

let providerAvailabilityRequestToken = 0;

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function parseDateTimeString(value) {
  if (!value || typeof value !== "string") {
    return null;
  }
  const normalized = value.replace(" ", "T");
  let date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    date = new Date(`${normalized}Z`);
  }
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTime(value) {
  if (!value) {
    return "";
  }

  if (value instanceof Date) {
    return value.toLocaleTimeString("es-ES", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const stringValue = String(value);
  const timeMatch = stringValue.match(/(\d{2}:\d{2})/);
  if (timeMatch) {
    return timeMatch[1];
  }

  const parsed = parseDateTimeString(stringValue);
  if (parsed) {
    return parsed.toLocaleTimeString("es-ES", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return stringValue;
}

function formatTimeRange(start, end) {
  const startPart = formatTime(start);
  const endPart = formatTime(end);
  if (startPart && endPart) {
    return `${startPart} - ${endPart}`;
  }
  return startPart || endPart || "Horario sin definir";
}

function formatDateDisplay(value) {
  if (!value) {
    return "";
  }

  const date = parseDateTimeString(`${value}T00:00:00`);
  if (!date) {
    return value;
  }

  return date.toLocaleDateString("es-ES", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatDateTimeDisplay(value) {
  const parsed = parseDateTimeString(value);
  if (!parsed) {
    return value || "";
  }
  return formatHumanReadable(parsed);
}

function getWeekdayName(index) {
  if (!Number.isInteger(index)) {
    return null;
  }
  if (index >= 1 && index <= 7) {
    return WEEKDAY_NAMES[(index - 1) % WEEKDAY_NAMES.length];
  }
  if (index >= 0 && index < WEEKDAY_NAMES.length) {
    return WEEKDAY_NAMES[index];
  }
  return null;
}

function renderWeeklyAvailability(weekly) {
  if (!Array.isArray(weekly) || weekly.length === 0) {
    return '<p class="mb-0 text-muted">Este proveedor no tiene disponibilidad semanal configurada.</p>';
  }

  const slotsByDay = new Map();
  weekly.forEach((slot) => {
    const weekdayIndex = Number(slot.weekday);
    const dayNameFromIndex = Number.isNaN(weekdayIndex)
      ? null
      : getWeekdayName(weekdayIndex);
    const dayName = dayNameFromIndex || `Día ${escapeHtml(slot.weekday)}`;
    if (!slotsByDay.has(weekdayIndex)) {
      slotsByDay.set(weekdayIndex, { dayName, slots: [] });
    }
    slotsByDay.get(weekdayIndex).slots.push(slot);
  });

  const sortedDays = Array.from(slotsByDay.entries()).sort((a, b) => {
    const first = Number(a[0]);
    const second = Number(b[0]);
    if (Number.isNaN(first) && Number.isNaN(second)) {
      return 0;
    }
    if (Number.isNaN(first)) {
      return 1;
    }
    if (Number.isNaN(second)) {
      return -1;
    }
    return first - second;
  });

  return sortedDays
    .map(([, data]) => {
      const items = data.slots
        .slice()
        .sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)))
        .map((slot) => {
          const location = slot.location
            ? `<span class="text-muted ms-2 flex-shrink-0">(${escapeHtml(slot.location)})</span>`
            : "";
          return `<li class="list-group-item px-0 py-1 d-flex flex-wrap justify-content-between align-items-center gap-2">
            <span>${escapeHtml(formatTimeRange(slot.start_time, slot.end_time))}</span>
            ${location}
          </li>`;
        })
        .join("");
      return `<div class="mb-3">
        <h4 class="h6 text-primary mb-1">${escapeHtml(data.dayName)}</h4>
        <ul class="list-group list-group-flush">
          ${items}
        </ul>
      </div>`;
    })
    .join("");
}

function renderUpcomingSlots(slots, timezone) {
  if (!Array.isArray(slots) || slots.length === 0) {
    return "";
  }

  const slotsByDate = new Map();

  slots.forEach((slot) => {
    const dateKey = slot.date || (slot.start_at ? String(slot.start_at).slice(0, 10) : null);
    if (!dateKey) {
      return;
    }

    if (!slotsByDate.has(dateKey)) {
      slotsByDate.set(dateKey, []);
    }

    slotsByDate.get(dateKey).push(slot);
  });

  if (!slotsByDate.size) {
    return "";
  }

  const timezoneNotice = timezone
    ? `<p class="text-muted small mb-2">Horario en ${escapeHtml(timezone)}.</p>`
    : "";

  const items = Array.from(slotsByDate.entries())
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([dateKey, daySlots]) => {
      const dayLabel = formatDateDisplay(dateKey);
      const rows = daySlots
        .slice()
        .sort((a, b) => String(a.start_at).localeCompare(String(b.start_at)))
        .map((slot) => {
          const summary = formatTimeRange(slot.start_at, slot.end_at);
          return `<li class="list-group-item px-0 py-1 d-flex justify-content-between align-items-center">
            <span>${escapeHtml(summary)}</span>
            <span class="badge text-bg-light">${escapeHtml(`${slot.slot_minutes || 30} min`)}</span>
          </li>`;
        })
        .join("");

      return `<div class="mb-3">
        <h4 class="h6 mb-1">${escapeHtml(dayLabel || dateKey)}</h4>
        <ul class="list-group list-group-flush">
          ${rows}
        </ul>
      </div>`;
    })
    .join("");

  return `<div>
    <h3 class="h6 text-success">Próximos horarios disponibles</h3>
    ${timezoneNotice}
    ${items}
  </div>`;
}

function renderAvailabilityExceptions(exceptions) {
  if (!Array.isArray(exceptions)) {
    return "";
  }
  const blocking = exceptions.filter((exception) => exception.is_blocking !== false);
  if (!blocking.length) {
    return "";
  }

  const items = blocking
    .slice()
    .sort((a, b) => String(a.start_at).localeCompare(String(b.start_at)))
    .map((exception) => {
      const startText = formatDateTimeDisplay(exception.start_at);
      const endText = formatDateTimeDisplay(exception.end_at);
      const reason = exception.reason
        ? ` <span class="text-muted">— ${escapeHtml(exception.reason)}</span>`
        : "";
      return `<li class="list-group-item px-0 py-1">
        <div>${escapeHtml(startText)}<span class="text-muted"> &rarr; </span>${escapeHtml(endText)}</div>
        ${reason}
      </li>`;
    })
    .join("");

  return `<div class="mt-3">
    <h4 class="h6 text-danger mb-1">Bloqueos programados</h4>
    <ul class="list-group list-group-flush">
      ${items}
    </ul>
  </div>`;
}

function updateProviderSelectionState() {
  if (clearProviderSelectionButton) {
    clearProviderSelectionButton.disabled = !appointmentProviderSelect.value;
  }
}

function resetProviderAvailabilityDisplay() {
  providerAvailabilityWrapper.classList.add("d-none");
  providerAvailabilityProviderName.textContent = "";
  providerAvailabilityContent.innerHTML =
    '<span class="text-muted">Selecciona un proveedor para consultar sus horarios disponibles.</span>';
  updateProviderSelectionState();
}

function showProviderAvailabilityLoading() {
  providerAvailabilityWrapper.classList.remove("d-none");
  providerAvailabilityProviderName.textContent = "Cargando...";
  providerAvailabilityContent.innerHTML =
    '<div class="text-muted small">Obteniendo disponibilidad...</div>';
}

async function loadProviderAvailability(providerId) {
  if (!providerId) {
    resetProviderAvailabilityDisplay();
    return;
  }

  providerAvailabilityRequestToken += 1;
  const requestId = providerAvailabilityRequestToken;
  showProviderAvailabilityLoading();

  try {
    const response = await fetch(`${API_BASE}/providers/${providerId}/availability`);
    const data = await handleResponse(response);

    if (requestId !== providerAvailabilityRequestToken) {
      return;
    }

    providerAvailabilityWrapper.classList.remove("d-none");
    const providerName =
      data?.provider?.display_name || data?.provider?.name || `Proveedor ${providerId}`;
    providerAvailabilityProviderName.textContent = providerName;

    const timezone = data?.timezone || data?.provider?.timezone;
    const upcomingHtml = renderUpcomingSlots(data?.upcoming_slots, timezone);
    const weeklyHtml = renderWeeklyAvailability(data?.weekly);
    const exceptionsHtml = renderAvailabilityExceptions(data?.exceptions);
    const sections = [upcomingHtml, weeklyHtml, exceptionsHtml].filter(Boolean);
    providerAvailabilityContent.innerHTML =
      sections.join('<hr class="my-2" />') ||
      '<p class="mb-0 text-muted">Este proveedor no tiene disponibilidad configurada.</p>';
  } catch (error) {
    if (requestId !== providerAvailabilityRequestToken) {
      return;
    }
    console.error("Error cargando disponibilidad", error);
    providerAvailabilityWrapper.classList.remove("d-none");
    providerAvailabilityProviderName.textContent = "";
    providerAvailabilityContent.innerHTML =
      '<p class="mb-0 text-danger">No se pudo cargar la disponibilidad del proveedor seleccionado.</p>';
  }
}

// ========== Gestión de pacientes ==========
async function loadPatients() {
  try {
    const response = await fetch(`${API_BASE}/patients`);
    const patients = await handleResponse(response);

    // Limpiar tabla y selectores
    patientsTableBody.innerHTML = "";
    appointmentPatientSelect.innerHTML = '<option value="" disabled selected>Selecciona un paciente</option>';

    patients.forEach((patient) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${patient.patient_id}</td>
        <td>${patient.first_name}</td>
        <td>${patient.last_name}</td>
        <td>${patient.email}</td>
        <td class="text-center">
          <button class="btn btn-sm btn-outline-danger" data-id="${patient.patient_id}">
            Eliminar
          </button>
        </td>
      `;
      patientsTableBody.appendChild(row);

      const option = document.createElement("option");
      option.value = patient.patient_id;
      option.textContent = `${patient.patient_id} - ${patient.first_name} ${patient.last_name}`;
      appointmentPatientSelect.appendChild(option);
    });
  } catch (error) {
    console.error("Error cargando pacientes", error);
  }
}

async function createPatient(event) {
  event.preventDefault();

  const firstName = document.getElementById("patient-first-name").value.trim();
  const lastName = document.getElementById("patient-last-name").value.trim();
  const email = document.getElementById("patient-email").value.trim();

  if (!firstName || !lastName || !email) {
    showFeedback("Completa todos los campos del paciente", "warning");
    alert("Completa todos los campos del paciente");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/patients`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
      }),
    });

    await handleResponse(response);
    showFeedback("Paciente creado correctamente", "success");
    document.getElementById("patient-form").reset();
    await loadPatients();
  } catch (error) {
    console.error("Error creando paciente", error);
  }
}

async function deletePatient(patientId) {
  if (!confirm("¿Eliminar paciente? Esta acción no se puede deshacer.")) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/patients/${patientId}`, {
      method: "DELETE",
    });

    await handleResponse(response);
    showFeedback("Paciente eliminado", "info");
    await loadPatients();
    await loadAppointments();
  } catch (error) {
    console.error("Error eliminando paciente", error);
  }
}

// ========== Gestión de proveedores ==========
async function loadProviders() {
  try {
    const previousProviderId = appointmentProviderSelect.value;
    const response = await fetch(`${API_BASE}/providers`);
    const providers = await handleResponse(response);

    appointmentProviderSelect.innerHTML = '<option value="" disabled selected>Selecciona un proveedor</option>';
    let hasPreviousProvider = false;
    providers.forEach((provider) => {
      const option = document.createElement("option");
      option.value = provider.provider_id;
      option.textContent = `${provider.provider_id} - ${provider.display_name || provider.name || "Proveedor"}`;
      appointmentProviderSelect.appendChild(option);
      if (String(provider.provider_id) === String(previousProviderId)) {
        hasPreviousProvider = true;
      }
    });

    if (hasPreviousProvider && previousProviderId) {
      appointmentProviderSelect.value = previousProviderId;
      loadProviderAvailability(previousProviderId);
    } else {
      resetProviderAvailabilityDisplay();
    }
    updateProviderSelectionState();
  } catch (error) {
    console.error("Error cargando proveedores", error);
    resetProviderAvailabilityDisplay();
  }
}

// ========== Gestión de citas ==========
const CANCELABLE_STATUSES = new Set(["booked", "rescheduled"]);

async function loadAppointments() {
  try {
    const response = await fetch(`${API_BASE}/appointments`);
    const appointments = await handleResponse(response);

    appointmentsTableBody.innerHTML = "";
    appointments.forEach((appointment) => {
      const row = document.createElement("tr");
      const isCancelable = CANCELABLE_STATUSES.has(appointment.status);
      row.innerHTML = `
        <td>${appointment.appointment_id}</td>
        <td>${appointment.patient_id}</td>
        <td>${appointment.provider_id}</td>
        <td>${appointment.start_at}</td>
        <td>${appointment.end_at}</td>
        <td><span class="badge text-bg-light">${appointment.status}</span></td>
        <td class="text-center">
          ${
            isCancelable
              ? `<button class="btn btn-sm btn-outline-warning" data-cancel-id="${appointment.appointment_id}">Cancelar</button>`
              : ""
          }
        </td>
      `;
      appointmentsTableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error cargando citas", error);
  }
}

function formatDateTimeLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function formatHumanReadable(date) {
  return date.toLocaleString("es-ES", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function updateAppointmentHiddenFields() {
  const dateValue = appointmentDateInput.value;
  const startTimeValue = appointmentStartTimeInput.value;
  const durationValue = DEFAULT_APPOINTMENT_DURATION_MINUTES;

  appointmentStartInput.value = "";
  appointmentEndInput.value = "";

  if (!appointmentTimeSummary) {
    return;
  }

  if (!dateValue || !startTimeValue) {
    appointmentTimeSummary.textContent =
      "Selecciona fecha y hora para reservar una cita de 30 minutos.";
    return;
  }

  const startDate = new Date(`${dateValue}T${startTimeValue}`);
  if (Number.isNaN(startDate.getTime())) {
    appointmentTimeSummary.textContent =
      "La combinación seleccionada no es válida. Revisa la fecha y hora.";
    return;
  }

  const endDate = new Date(startDate.getTime() + durationValue * 60 * 1000);

  appointmentStartInput.value = `${dateValue}T${startTimeValue}`;
  appointmentEndInput.value = formatDateTimeLocal(endDate);
  [appointmentDateInput, appointmentStartTimeInput].forEach((field) =>
    field.classList.remove("is-invalid")
  );
  appointmentTimeSummary.textContent = `Cita desde ${formatHumanReadable(
    startDate
  )} hasta ${formatHumanReadable(endDate)} (30 minutos).`;
}

function resetAppointmentFieldValidity() {
  [
    appointmentPatientSelect,
    appointmentProviderSelect,
    appointmentDateInput,
    appointmentStartTimeInput,
  ].forEach((field) => field.classList.remove("is-invalid"));
}

function flagMissingAppointmentFields(missingFields) {
  missingFields.forEach(({ element }) => {
    element.classList.add("is-invalid");
  });
}

async function createAppointment(event) {
  event.preventDefault();

  resetAppointmentFieldValidity();

  const patientId = appointmentPatientSelect.value;
  const providerId = appointmentProviderSelect.value;
  const dateValue = appointmentDateInput.value;
  const startTimeValue = appointmentStartTimeInput.value;

  updateAppointmentHiddenFields();

  const startAt = appointmentStartInput.value;
  const endAt = appointmentEndInput.value;

  const missingFields = [
    { element: appointmentPatientSelect, label: "Paciente", value: patientId },
    { element: appointmentProviderSelect, label: "Proveedor", value: providerId },
    { element: appointmentDateInput, label: "Fecha", value: dateValue },
    {
      element: appointmentStartTimeInput,
      label: "Hora de inicio",
      value: startTimeValue,
    },
  ].filter((field) => !field.value);

  if (missingFields.length) {
    flagMissingAppointmentFields(missingFields);
    const missingLabels = missingFields.map(({ label }) => label).join(", ");
    const message = `Completa los siguientes campos: ${missingLabels}`;
    showFeedback(message, "warning");
    alert(message);
    return;
  }

  if (!startAt || !endAt) {
    const message =
      "Selecciona una combinación válida de fecha y hora para la cita.";
    showFeedback(message, "warning");
    alert(message);
    [appointmentDateInput, appointmentStartTimeInput].forEach((field) =>
      field.classList.add("is-invalid")
    );
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/appointments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_id: Number(patientId),
        provider_id: Number(providerId),
        start_at: startAt,
        end_at: endAt,
      }),
    });

    await handleResponse(response);
    showFeedback("Cita creada correctamente", "success");
    appointmentForm.reset();
    updateAppointmentHiddenFields();
    resetAppointmentFieldValidity();
    await loadAppointments();
  } catch (error) {
    console.error("Error creando cita", error);
  }
}

async function cancelAppointment(appointmentId) {
  if (!confirm("¿Cancelar la cita seleccionada?")) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/appointments/${appointmentId}/cancel`, {
      method: "POST",
    });

    await handleResponse(response);
    showFeedback("Cita cancelada correctamente", "info");
    await loadAppointments();
  } catch (error) {
    console.error("Error cancelando cita", error);
  }
}

// ========== Listeners y arranque ==========
document.addEventListener("DOMContentLoaded", () => {
  loadPatients();
  loadProviders();
  loadAppointments();

  document.getElementById("patient-form").addEventListener("submit", createPatient);
  appointmentForm.addEventListener("submit", createAppointment);
  appointmentForm.addEventListener("reset", () => {
    updateAppointmentHiddenFields();
    resetAppointmentFieldValidity();
    resetProviderAvailabilityDisplay();
  });
  document.getElementById("refresh-patients").addEventListener("click", loadPatients);
  document.getElementById("refresh-appointments").addEventListener("click", loadAppointments);

  appointmentProviderSelect.addEventListener("change", (event) => {
    const providerId = event.target.value;
    updateProviderSelectionState();
    if (!providerId) {
      resetProviderAvailabilityDisplay();
      return;
    }
    loadProviderAvailability(providerId);
  });

  if (clearProviderSelectionButton) {
    clearProviderSelectionButton.addEventListener("click", () => {
      appointmentProviderSelect.selectedIndex = 0;
      appointmentProviderSelect.classList.remove("is-invalid");
      appointmentProviderSelect.dispatchEvent(
        new Event("change", { bubbles: true })
      );
    });
  }

  // Delegación de eventos para eliminar pacientes desde la tabla
  patientsTableBody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) return;
    const patientId = button.getAttribute("data-id");
    deletePatient(patientId);
  });

  appointmentsTableBody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-cancel-id]");
    if (!button) return;
    const appointmentId = button.getAttribute("data-cancel-id");
    cancelAppointment(appointmentId);
  });

  [appointmentDateInput, appointmentStartTimeInput].forEach((field) => {
    field.addEventListener("change", updateAppointmentHiddenFields);
    field.addEventListener("input", updateAppointmentHiddenFields);
  });

  updateAppointmentHiddenFields();
  updateProviderSelectionState();
});
    
