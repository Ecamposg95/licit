"""Protección contra SSRF para toda URL que llegue de un usuario o de una fuente externa.

- Solo `https`, sin credenciales en la URL y en el puerto 443.
- El host debe ser exactamente un dominio permitido o un subdominio suyo.
- Todas las IP a las que resuelve deben ser públicas: se bloquean privadas, loopback, link-local (incluida
  169.254.169.254, la de metadatos de la nube), espacio compartido, reservadas, multicast e IPv6 ULA.
- `safe_get` sigue a mano cada redirección y vuelve a validar cada salto antes de conectarse.

Límite conocido: entre la validación y la conexión el nombre se vuelve a resolver (rebinding de DNS). El riesgo es
bajo porque solo se aceptan dominios de la lista blanca, cuyo DNS no controla quien envía la URL.
"""
import ipaddress
import socket

import httpx

from app.core.errors import AppError

USER_AGENT = "LicitDemo/1.0 (+contacto Atlas Technologies)"
_MAX_URL = 2000
_DROP_HEADERS = {"content-encoding", "content-length", "transfer-encoding"}


def resolve_host(host: str) -> list[str]:
    """IP a las que resuelve el host (se sustituye en las pruebas para no usar la red)."""
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _is_public(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified or ip.is_loopback
                                 or ip.is_link_local or ip.is_private)


def _reject(message: str) -> AppError:
    return AppError(422, "url_not_allowed", message)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def validate_public_url(url: str, allowed_domains: list[str]) -> str:
    """Devuelve la URL normalizada o lanza `AppError(422, "url_not_allowed")`."""
    if not isinstance(url, str) or not url.strip() or len(url) > _MAX_URL:
        raise _reject("La URL está vacía o es demasiado larga")
    try:
        parsed = httpx.URL(url.strip())
    except Exception:
        raise _reject("La URL no es válida") from None
    if parsed.scheme != "https":
        raise _reject("Solo se aceptan direcciones https")
    if parsed.userinfo:
        raise _reject("La URL no puede llevar usuario ni contraseña")
    host = (parsed.host or "").lower().rstrip(".")
    if not host:
        raise _reject("La URL no tiene dominio")
    if parsed.port not in (None, 443):
        raise _reject("Solo se acepta el puerto estándar de https (443)")
    allowed = [d.strip().lower().rstrip(".") for d in allowed_domains if d and d.strip()]
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise _reject(f"El dominio {host} no está en la lista de fuentes permitidas")
    if _is_ip_literal(host):
        addresses = [host]
    else:
        try:
            addresses = resolve_host(host)
        except (OSError, UnicodeError):
            addresses = []
    if not addresses:
        raise _reject(f"No se pudo resolver el dominio {host}")
    if not all(_is_public(a) for a in addresses):
        raise _reject(f"El dominio {host} apunta a una dirección interna; no se consulta")
    return str(parsed.copy_with(host=host))


def _new_client(timeout: httpx.Timeout) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=False)


def safe_get(url: str, allowed_domains: list[str], max_bytes: int = 5_000_000, max_redirects: int = 3,
             timeout: tuple[float, float] = (10, 20), *, client: httpx.Client | None = None) -> httpx.Response:
    """GET con validación SSRF en cada salto, límite de tamaño y sin seguir redirecciones a ciegas.

    Devuelve la respuesta final ya leída (cualquier código que no sea redirección). Errores:
    422 `url_not_allowed` (URL o redirección no permitida), 422 `response_too_large` y 502 `source_unavailable`.
    """
    connect, read = timeout
    http = client or _new_client(httpx.Timeout(read, connect=connect))
    try:
        current = validate_public_url(url, allowed_domains)
        for _hop in range(max_redirects + 1):
            request = http.build_request("GET", current, headers={"User-Agent": USER_AGENT})
            try:
                response = http.send(request, stream=True, follow_redirects=False)
            except httpx.TransportError as exc:
                raise AppError(502, "source_unavailable",
                               f"No se pudo descargar de {request.url.host} ({type(exc).__name__})") from None
            try:
                location = response.headers.get("Location")
                if response.is_redirect and location:
                    current = validate_public_url(str(response.url.join(location)), allowed_domains)
                    continue
                body = bytearray()
                try:
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise AppError(422, "response_too_large",
                                           f"La respuesta supera el límite de {max_bytes} bytes")
                except httpx.TransportError as exc:
                    raise AppError(502, "source_unavailable",
                                   f"La descarga de {request.url.host} se interrumpió ({type(exc).__name__})") from None
                headers = [(k, v) for k, v in response.headers.multi_items() if k.lower() not in _DROP_HEADERS]
                return httpx.Response(response.status_code, headers=headers, content=bytes(body), request=request)
            finally:
                response.close()
        raise _reject(f"Demasiadas redirecciones (más de {max_redirects})")
    finally:
        if client is None:
            http.close()
