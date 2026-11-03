# Operación del beta (Railway)

Proyecto `licit-dipromedic` · servicios `web` y `Postgres` · https://web-production-9afcc.up.railway.app
Las variables `R` de abajo evitan repetir los identificadores:

```bash
R="--project c9c57e25-7e6d-45bf-89d6-361eb5647a96 --environment production"
```

La base de Postgres **no tiene URL pública**. Todo se hace dentro de los contenedores con `railway ssh`.

## 1. Respaldo de la base

Antes de cada despliegue con migraciones y al menos una vez por semana durante el beta. Desde una carpeta del FS de
Linux (no `/mnt/c`):

```bash
F=licit-$(date +%Y%m%d-%H%M).sql.gz
railway ssh $R --service Postgres -- sh -c 'pg_dump -U "$PGUSER" -d "$PGDATABASE" --no-owner --no-acl | gzip | base64 -w0' \
  | base64 -d > "$F" && gzip -t "$F" && ls -la "$F"
```

El `base64` evita que la terminal remota altere bytes binarios. `gzip -t` confirma que llegó completo. Guarda el
archivo fuera de la laptop (Drive de Atlas, carpeta restringida). Contiene correos, bitácora y lo que capturen los
testers. No lo compartas.

**Lo que no incluye:** los archivos del bucket (`OBJECT_STORAGE_BUCKET`). La base guarda su ruta y su SHA-256. Si se
pierde el bucket, los documentos quedan registrados pero no se pueden descargar. Los archivos semilla se reponen solos
al arrancar (`ensure_demo_files`). Los que suban los testers no.

## 2. Restauración

Ensayada el 2026-11-02 en local: 22 tablas con conteos idénticos, Alembic en head, bootstrap idempotente y login
correcto. Para producción:

1. Respalda primero el estado actual (paso 1). Una restauración no se deshace.
2. Detén el tráfico: en Railway, escala `web` a 0 réplicas (o pausa el servicio).
3. Recrea el esquema y carga el respaldo:
   ```bash
   railway ssh $R --service Postgres -- sh -c 'psql -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 \
     -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
   base64 -w0 "$F" | railway ssh $R --service Postgres -- sh -c \
     'base64 -d | gunzip | psql -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -q'
   ```
4. Vuelve a levantar `web`. El arranque corre `alembic upgrade head` y `bootstrap.py`, que no tocan datos existentes.
5. Verifica que puedas entrar con `presentador` y que el radar muestre las oportunidades.

Restaurar en local para revisar un respaldo:
`gunzip -c "$F" | docker exec -i licit-pg-test psql -U postgres -d <base_nueva> -v ON_ERROR_STOP=1 -q`.

## 3. Cuentas de los testers

Se operan con `scripts/cuentas.py` dentro del contenedor `web`. Cada cambio queda en la bitácora (Gobierno →
historial).

```bash
railway ssh $R --service web -- python scripts/cuentas.py listar
railway ssh $R --service web -- python scripts/cuentas.py desactivar analista3@dipromedic.example
railway ssh $R --service web -- python scripts/cuentas.py activar analista3@dipromedic.example
railway ssh $R --service web -- python scripts/cuentas.py vence analista3@dipromedic.example 2026-11-30   # fin del día, CDMX
railway ssh $R --service web -- python scripts/cuentas.py vence analista3@dipromedic.example nunca
```

Para cambiar una contraseña, abre una sesión interactiva (`railway ssh $R --service web`) y corre
`python scripts/cuentas.py contrasena <correo>`, o `--demo` para todas las cuentas demo. La contraseña se pide en la
terminal (mínimo 10 caracteres) y nunca va en los argumentos.

| Necesito… | Hago… | Efecto |
|---|---|---|
| Quitar el acceso a un tester | `desactivar` | Inmediato, también corta su sesión abierta |
| Acceso temporal | `vence <correo> AAAA-MM-DD` | Al vencer ya no entra y su sesión se corta |
| La contraseña se filtró | `contrasena --demo` y luego rotar `SESSION_SECRET` | La contraseña nueva aplica ya. Las sesiones abiertas duran hasta 8 h (`SESSION_TTL_MINUTES`) salvo que rotes el secreto |

**Ojo:** cambiar `DEMO_USER_PASSWORD` en Railway **no** cambia las contraseñas de cuentas que ya existen. Solo se usa
al crear cuentas nuevas.

## 4. Rotar secretos

- `SESSION_SECRET`: cámbialo en las variables de `web` (`railway variables $R --service web --set SESSION_SECRET=…`).
  El redeploy invalida todas las sesiones y cada quien vuelve a entrar.
- Credenciales del bucket (`OBJECT_STORAGE_*`): rótalas en el bucket de Railway y actualiza las variables de `web`.

## 5. Datos de prueba

- `python scripts/bootstrap.py --reset` reinicia el escenario demo y **borra lo que capturaron los testers** sobre
  datos ficticios. Los registros REAL no se tocan. No lo corras durante el beta sin avisar y sin respaldo previo.
- Al cerrar el beta, haz un respaldo final, desactiva las cuentas (`desactivar`) y luego decide si reinicias.

## 6. Despliegue

Ver `CLAUDE.md` (copiar a un directorio de Linux y `railway up` desde ahí). Respalda antes si el cambio trae una
migración nueva (`alembic/versions`).
