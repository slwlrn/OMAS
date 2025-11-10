# SRS-OMAS v3 Summary

## Document Metadata
- **Title:** Software Requirements Specification for OMAS (Online Medical Appointment System)
- **Version:** 1.0 (final release on 21/09/2025)
- **Authors:** Daniel Garcia Soni, Carlos Ochoa Gonzalez, Juan José Ponce Estrada, Tonatiuh Salas Ortiz (Group 47)
- **Course/Advisor:** Análisis, diseño y construcción de software — Prof. Perla Angélica García Aguirre

## Purpose and Scope
- Defines functional and non-functional requirements for a two-sided medical appointment platform serving patients and healthcare providers via responsive web and mobile clients.
- Covers scheduling, notification workflows, secure data handling, and operational support needs for clinics and hospitals.

## Key Stakeholders & Audience
- Healthcare administrators/clients for alignment with organizational goals.
- Development and testing teams as the baseline for implementation and validation.
- End users (patients, doctors/providers) to confirm usability expectations.

## Product Overview
- Patient-facing web/mobile app for discovery and booking.
- Provider portal for availability management, schedule visualization, outcome tracking, and reporting.
- Backend communicates over HTTPS with a relational database; messaging queue supports notifications.
- Integrates optional services (SMS/email gateways, payment processors, EHR APIs when available).

## Requerimientos básicos para demo básica
- **Acceso y perfiles esenciales:** Registro e inicio de sesión de pacientes y proveedores (F1–F2) con edición mínima del perfil para operar el flujo de citas.
- **Descubrimiento y reservación inicial:** Buscador por especialidad/ubicación con disponibilidad básica (F3) que permita agendar una cita simple desde web o móvil (F4).
- **Confirmaciones esenciales:** Notificación transaccional de creación/cancelación de cita por email o SMS (F6) para garantizar comunicación mínima.
- **Disponibilidad mínima del proveedor:** Definir horarios regulares y cerrar espacios puntuales (F11) con vista diaria básica de agenda (F12).
- **Seguimiento básico de cita:** Marcar la cita como atendida o cancelada y capturar un comentario corto (F13) para mostrar el ciclo completo.
- **Operación centralizada:** Vista administrativa ligera para monitorear la lista de citas del día y su estado (F9) sin métricas avanzadas.
- **Paridad en clientes críticos:** Las funciones esenciales del demo (crear cuentas, reservar, gestionar disponibilidad, recibir confirmaciones) operan igual en web y app móvil (F17).

## Requerimientos opcionales
- **Gestión completa de agenda:** Reagendar y cancelar por parte del paciente con reglas de negocio, así como bloqueos recurrentes complejos (F4–F5, F11 ampliado).
- **Notificaciones configurables:** Definir preferencias, ventanas y reintentos parametrizables para cada usuario (F14–F15) con múltiples canales.
- **Prevención avanzada de conflictos:** Reglas inteligentes para evitar traslapes, manejo de listas de espera y exportación a iCal/Google Calendar (F18–F19).
- **Integraciones externas:** Conectores con pasarelas de pago, historiales clínicos (EHR) y servicios de mensajería enriquecida descritos como futuras extensiones.
- **Reportes y analítica:** Dashboards históricos, comparativas entre proveedores, descargas ofimáticas y métricas de utilización avanzadas (F10 ampliado).
- **Gobernanza y cumplimiento extendidos:** Bitácoras detalladas, automatización de operaciones, soporte multi-sede completo y procesos de mantenimiento de catálogos.

## Use Cases (U1–U8)
- **Patient flows:** Book (U1), reschedule (U2), cancel (U3) appointments, and receive notifications (U4) with alternative flows for conflicts, policy limits, or delivery failures.
- **Provider flows:** Manage availability (U5), view schedules (U6), confirm completion or no-shows with notes (U7), and configure notification preferences (U8).

## Non-Functional Requirements
- **Performance:** API p95 ≤ 3s under 500 concurrent users; slot search first page ≤ 2s; notification queuing ≤ 500ms; sustain ≥ 50 appointments/min for 10 minutes.
- **Security & Safety:** TLS 1.2+ with HSTS, encryption at rest, mandatory 2FA for providers/admins, RBAC with rate limiting and anti-bot protections, session rotation, and regulatory-compliant audit retention.
- **Quality Attributes:** Reliability (99.5% uptime, zero loss of confirmed bookings), usability (≤3 steps to book, WCAG 2.1 AA), maintainability (API versioning, ≥70% core test coverage), portability (recent browsers, iOS/Android), scalability (stateless APIs, worker queues, read replicas).

## Additional Requirements
- **Internationalization:** Launch support for English and Spanish; localized resources stored externally; times stored in UTC and localized per user.
- **Privacy & Legal:** Compliance with HIPAA-equivalent/GDPR principles; explicit user consent; accessible privacy/terms pages.
- **Maintenance & Support:** Ticketing process with ≤24h response for standard issues; quarterly maintenance releases minimum.
- **Integration & Interoperability:** RESTful APIs for third parties, provider iCal exports, and accompanying integration documentation.
- **Accessibility & Usability:** Enforce WCAG 2.1 AA and ensure booking flow remains simple (≤3 steps).

## Data Dictionary Highlights
- Core entities include patient, provider, appointment, availability rules, exception windows, notification preferences, and audit events, each keyed by UUIDs and linked to the corresponding functional requirements.

## Assumptions & Constraints
- Users have reliable internet access; clinics supply accurate availability data.
- Technology stack includes relational databases (PostgreSQL/MySQL), RESTful APIs with JWT sessions, and queues for notification retries.
- Mobile and web experiences must maintain P0 feature parity and comply with UML/COMET modeling constraints defined by the course.

