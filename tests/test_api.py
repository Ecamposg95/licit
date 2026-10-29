LIC = {
    "numero_procedimiento": "LA-50-GYR-050GYR019-N-123-2026",
    "titulo": "Adquisición de material de osteosíntesis",
    "dependencia": "IMSS",
    "entidad_federativa": "Querétaro",
    "fecha_apertura": "2026-11-15T10:00:00-06:00",
    "monto_estimado": "1250000.50",
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_bad_password(client, admin_headers):
    r = client.post("/api/auth/login", data={"username": "admin@test.mx", "password": "nope"})
    assert r.status_code == 401


def test_me(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_requires_auth(client):
    assert client.get("/api/licitaciones").status_code == 401


def test_crud_licitacion(client, admin_headers):
    r = client.post("/api/licitaciones", json=LIC, headers=admin_headers)
    assert r.status_code == 201, r.text
    lic = r.json()
    assert lic["estatus"] == "detectada"
    assert lic["tipo"] == "licitacion_publica"

    assert client.post("/api/licitaciones", json=LIC, headers=admin_headers).status_code == 409

    r = client.patch(f"/api/licitaciones/{lic['id']}", json={"estatus": "en_analisis"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["estatus"] == "en_analisis"

    r = client.get("/api/licitaciones", params={"q": "osteosíntesis"}, headers=admin_headers)
    assert [x["id"] for x in r.json()] == [lic["id"]]
    r = client.get("/api/licitaciones", params={"estatus": "ganada"}, headers=admin_headers)
    assert r.json() == []

    assert client.delete(f"/api/licitaciones/{lic['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/licitaciones/{lic['id']}", headers=admin_headers).status_code == 404


def test_viewer_cannot_create(client, viewer_headers):
    r = client.post("/api/licitaciones", json=LIC, headers=viewer_headers)
    assert r.status_code == 403


def test_invalid_estatus_rejected(client, admin_headers):
    r = client.post("/api/licitaciones", json={**LIC, "estatus": "inventado"}, headers=admin_headers)
    assert r.status_code == 422
