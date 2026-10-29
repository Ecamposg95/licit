# Informe de limitaciones

Se actualiza en cada entrega. Corte: 2026-10-28 (E1).

## Fuentes

| Fuente | Estado | Evidencia |
|---|---|---|
| DOF vía SIDOF (`sidof.segob.gob.mx/notas/docFuente/…`) | Accesible desde el servidor de desarrollo | HTTP 200 en ~1.8 s. Adaptador pendiente (E2) |
| SIDOF portada | Lenta | Más de 20 s sin respuesta completa |
| `www.dof.gob.mx` | No accesible desde el entorno de desarrollo | Sin respuesta HTTP; falta probar desde Railway |
| Compras MX · difusión | Accesible, pero es una SPA | Devuelve una página vacía de 4 KB; no hay API pública verificada. No se inventan endpoints |
| IMSS licitaciones | No probada | — |

No se ha confirmado una oportunidad compatible abierta. Las tres referencias del pack son históricas y tienen la
fecha de presentación transcurrida; su resultado es desconocido.

## Funciones

- Sin búsqueda en vivo todavía (E2). El botón «Buscar ahora» está deshabilitado y lo explica; nunca se rellena con fixtures.
- Sin IA. La extracción de requisitos será manual o por reglas, con página y fragmento.
- Los documentos semilla son solo metadatos. Los archivos con marca DEMO llegan en E2/E3.
- Afinidad y correspondencia técnica pendientes (E3). El radar muestra «—» y explica por qué.
- No se presentan ofertas, no se firman documentos y no se envían mensajes. Está fuera del alcance.

## Capacidad

Sin medir. El objetivo del pack (10 usuarios concurrentes, 500 oportunidades, p95 < 2 s) se mide en E4.
