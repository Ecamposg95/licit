"""B2: API del catálogo (/api/v1/catalog): líneas, productos, detalle con citas."""
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import DataKind, Organization, Product, Variant
from app.services.catalog_import import CATALOG_PATH, import_catalog
from tests.conftest import login

REAL = DataKind.REAL.value
ALP35 = "traufix_extremidad-superior_placa-bloqueada-alp"
TITAN = "traufix_extremidad-superior_titan"


@pytest.fixture
def catalog():
    """Importa el catálogo REAL y hace commit antes de llamar a la API (la bitácora toma un candado)."""
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    import_catalog(db, org.id, CATALOG_PATH)
    db.commit()
    ids = {p.external_ref: p.id for p in db.scalars(select(Product).where(Product.data_kind == REAL))}
    db.close()
    return ids


def _get(client, headers, path, **params):
    return client.get(f"/api/v1/catalog{path}", headers=headers, params=params)


def test_catalog_api_filters_line_and_code_search(client, analista, catalog):
    # Líneas con su número de productos y sus familias.
    r = _get(client, analista, "/lines")
    assert r.status_code == 200, r.text
    lines = {x["line"]: x for x in r.json()}
    assert set(lines) == {"Traufix", "Corentec", "Biotechni", "Caleb", "Imedicom", "Anton-Hipp",
                          "IOT – Innovative Orthopedic Technologies"}
    assert lines["Traufix"]["product_count"] == 95 and lines["Corentec"]["product_count"] == 12
    assert lines["Corentec"]["families"] == ["Cadera", "Columna", "Hombro", "Rodilla"]
    assert sum(x["product_count"] for x in lines.values()) == 116
    assert r.json()[0]["line"] == "Traufix"  # la línea con más productos va primero

    # Filtro por línea y por familia.
    corentec = _get(client, analista, "/products", line="Corentec").json()
    assert len(corentec) == 12 and {c["line"] for c in corentec} == {"Corentec"}
    assert {c["data_kind"] for c in corentec} == {"REAL"}
    assert len(_get(client, analista, "/products", family="Cadera").json()) == 10

    # Búsqueda por código: «198» encuentra la placa ALP 3.5 (SKU DPM-198).
    found = _get(client, analista, "/products", q="198").json()
    assert catalog[ALP35] in {p["id"] for p in found}
    # También por nombre, sin importar mayúsculas, y con la letra cirílica que trae el sitio.
    assert catalog[TITAN] in {p["id"] for p in _get(client, analista, "/products", q="titan").json()}
    peek = _get(client, analista, "/products", q="STRAUFIX-РКА-0351").json()
    assert [p["id"] for p in peek] == [catalog["traufix_sports-medicine_anclas-ancla-peek-con-aguja"]]
    # Los comodines de LIKE se toman como texto.
    assert _get(client, analista, "/products", q="%").json() == []
    assert _get(client, analista, "/products", q="zzz-no-existe").json() == []


def test_catalog_card_fields_and_data_kind_filter(client, analista, catalog):
    cards = {c["id"]: c for c in _get(client, analista, "/products", line="Traufix").json()}
    titan = cards[catalog[TITAN]]
    assert titan["variant_count"] == 4
    assert titan["source_url"].startswith("https://www.dipromedic.com/")
    assert titan["checked_on"] == "2026-10-28"
    assert "DIPROMEDIC S.A. DE C.V." in titan["attribution"]
    assert titan["images"] and all(u.startswith("https://") for u in titan["images"])
    assert titan["review_status"] == "pendiente" and titan["subfamily"]
    assert "variants" not in titan  # la lista no arrastra las variantes
    assert cards[catalog["traufix_extremidad-superior_clavilock-con-gancho"]]["review_status"] == "por_revisar"

    synthetic = _get(client, analista, "/products", data_kind="SYNTHETIC").json()
    assert len(synthetic) == 6 and {p["data_kind"] for p in synthetic} == {"SYNTHETIC"}
    assert all(p["line"] is None and p["variant_count"] > 0 for p in synthetic)
    both = _get(client, analista, "/products", data_kind=["REAL", "SYNTHETIC"]).json()
    assert len(both) == 116 + 6
    assert len(_get(client, analista, "/products").json()) == 116 + 6


def test_product_detail_has_citations(client, analista, catalog):
    for ref, product_id in catalog.items():
        r = _get(client, analista, f"/products/{product_id}")
        assert r.status_code == 200, (ref, r.text)
        detail = r.json()
        for key, attr in detail["attributes"].items():
            assert attr["source_text"], (ref, key)
        for v in detail["variants"]:
            assert v["price"] is None and v["stock_demo"] is None and v["regulatory_reference"] is None
            assert v["field_provenance"] == {}
            for key, attr in v["attributes"].items():
                assert attr["source_text"], (ref, v["sku"], key)
        assert detail["variant_count"] == len(detail["variants"])

    titan = _get(client, analista, f"/products/{catalog[TITAN]}").json()
    assert titan["features"][0] == "Fabricada en aleación de Titanio (Ti6Al4V ELI, ASTM F136)."
    assert titan["data_quality_notes"] == []
    assert titan["documents"] == []
    # Los atributos comunes a todas las variantes van una sola vez; los de cada fila (orificios) quedan en la variante.
    assert titan["attributes"]["material"]["source_text"] == "Fabricada en aleación de Titanio (Ti6Al4V ELI, ASTM F136)."
    assert "holes" not in titan["attributes"]
    by_sku = {v["sku"]: v for v in titan["variants"]}
    assert set(by_sku) == {"DPM-569", "DPM-570", "DPM-571", "DPM-572"}
    assert by_sku["DPM-570"]["side"] == "izquierda" and by_sku["DPM-569"]["side"] == "derecha"
    assert by_sku["DPM-570"]["attributes"]["holes"]["values"] == [4, 6, 8, 10]
    assert by_sku["DPM-572"]["attributes"]["holes"]["values"] == [3, 5]
    assert by_sku["DPM-570"]["source_text"].startswith("Versión Izq. (Cód. 570)")

    flawed = _get(client, analista, f"/products/{catalog['traufix_extremidad-superior_clavilock-con-gancho']}").json()
    assert flawed["review_status"] == "por_revisar"
    assert len(flawed["data_quality_notes"]) == 4  # 2 del sitio y 2 de la importación (SKU 143 y 142 repetidos)


def test_detail_lists_only_documents_of_that_product(client, analista, catalog):
    from app.models import Document
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    db.add(Document(organization_id=org.id, title="Técnica quirúrgica TITAN", scope="producto",
                    data_kind=REAL, product_id=catalog[TITAN]))
    db.add(Document(organization_id=org.id, title="Otro producto", scope="producto",
                    data_kind=REAL, product_id=catalog[ALP35]))
    db.commit()
    db.close()
    docs = _get(client, analista, f"/products/{catalog[TITAN]}").json()["documents"]
    assert [d["title"] for d in docs] == ["Técnica quirúrgica TITAN"]
    assert docs[0]["product_id"] == catalog[TITAN]


def test_synthetic_product_detail_has_no_fake_citations(client, analista, catalog):
    synthetic = _get(client, analista, "/products", data_kind="SYNTHETIC").json()[0]
    detail = _get(client, analista, f"/products/{synthetic['id']}").json()
    assert detail["data_kind"] == "SYNTHETIC" and detail["variants"]
    assert detail["variants"][0]["price"] is not None  # precio ficticio, marcado como tal por data_kind
    assert detail["source_url"] is None and detail["checked_on"] is None and detail["images"] == []


def test_catalog_requires_login_and_isolates_organizations(client, analista, catalog):
    assert client.get("/api/v1/catalog/products").status_code == 401
    assert client.get("/api/v1/catalog/lines").status_code == 401
    assert _get(client, analista, "/products/no-existe").status_code == 404

    db = SessionLocal()
    other = Organization(name="Otra organización")
    db.add(other)
    db.flush()
    foreign = Product(organization_id=other.id, name="Producto ajeno", family="X", data_kind=REAL)
    db.add(foreign)
    db.commit()
    foreign_id = foreign.id
    db.close()
    assert _get(client, analista, f"/products/{foreign_id}").status_code == 404
    assert foreign_id not in {p["id"] for p in _get(client, analista, "/products").json()}
    assert "Producto ajeno" not in {p["name"] for p in _get(client, analista, "/products").json()}


def test_detail_of_a_ficha_without_codes_shows_its_cited_attributes(client, analista, catalog):
    stem = _get(client, analista, f"/products/{catalog['corentec_cadera_vastago-id-stem']}").json()
    assert stem["variants"] == [] and stem["variant_count"] == 0
    assert stem["attributes"]["cono"]["value"] == "12/14"
    assert stem["attributes"]["cono"]["source_text"].startswith("Recubrimiento Spray porus")
    assert "variantes_fijacion" not in stem["attributes"]  # su cita era el nombre de la ficha
    titan = _get(client, analista, f"/products/{catalog[TITAN]}").json()
    assert "region_anatomica" not in titan["attributes"]
    assert titan["attributes"]["material"]["source_text"]


def test_code_search_does_not_match_the_sku_prefix(client, analista, catalog):
    db = SessionLocal()
    org = db.scalars(select(Organization)).first()
    products = list(db.scalars(select(Product).where(Product.organization_id == org.id)))
    skus = {p.id: [v.sku for v in p.variants] for p in products}

    def expected(q: str) -> set[str]:
        out = set()
        for p in products:
            code_parts = [s[4:] if s.startswith("DPM-") else s for s in skus[p.id]]
            if q.lower() in p.name.lower() or any(q.upper() in c for c in code_parts):
                out.add(p.id)
        return out

    db.close()
    found = {p["id"] for p in _get(client, analista, "/products", q="d").json()}
    assert found == expected("d")
    with_variants = {pid for pid, s in skus.items() if s}
    # Antes «d» (la de «DPM-») traía todas las fichas con códigos; ahora quedan fuera las que no la tienen.
    assert with_variants - found
    # El prefijo se puede escribir: «DPM-198» equivale a «198».
    assert {p["id"] for p in _get(client, analista, "/products", q="DPM-198").json()} == expected("198")
    assert _get(client, analista, "/products", q="dpm-").json() == []
