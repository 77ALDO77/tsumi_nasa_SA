import json
from pathlib import Path

import numpy as np
import pytest
import httpx

from analisis import modis


def test_ndvi_masks_quality_land_clouds_historical_fill_and_range():
    raw = np.array([3000] * 11 + [-3000, -2001, 10001, -2000, 10000], dtype="int16")
    qa = np.full(raw.shape, 1 << 11, dtype="uint16")  # guía C61: bits 11-13 iguales a MOD13A2
    reliability = np.zeros(raw.shape, dtype="int8")
    reliability[1:6] = [-1, 1, 2, 3, 4]
    qa[6] |= 1
    qa[7] = 2 << 11  # costa
    qa[8] |= 1 << 8
    qa[9] |= 1 << 10
    qa[10] = 65535
    out = modis.filtrar(raw, {"valid_range": [-2000, 10000], "_FillValue": -3000,
                              "scale_factor": 10000, "add_offset": 0}, qa, reliability)
    np.testing.assert_allclose(out[[0, 14, 15]], [0.3, -0.2, 1])
    assert np.isnan(out[1:14]).all()


def test_lst_qc_zero_is_valid_but_fill_and_other_quality_are_not():
    raw = np.array([15000] * 7 + [0, 7499, 7500, 65535], dtype="uint16")
    qa = np.array([0, 1, 2, 3, 128, 64, 13, 0, 0, 0, 0], dtype="uint8")
    out = modis.filtrar(raw, {"valid_range": [7500, 65535], "_FillValue": 0,
                              "scale_factor": 0.02, "add_offset": 0}, qa)
    np.testing.assert_allclose(out[[0, 1, 5, 6, 9, 10]], [300, 300, 300, 300, 150, 1310.7])
    assert np.isnan(out[[2, 3, 4, 7, 8]]).all()


def test_aggregation_preserves_missingness_and_month_counts():
    ndvi = [np.array([[.2, np.nan, np.nan]]), np.array([[.4, .1, np.nan]])]
    out = modis.combinar(ndvi, ndvi, ndvi)
    np.testing.assert_allclose(out["ndvi_max"], [[.4, .1, np.nan]], equal_nan=True)
    np.testing.assert_equal(out["ndvi_n"], [[2, 1, 0]])
    assert out["lst_noche_min_k"][0, 0] == .2


def test_cell_screen_requires_at_least_one_fully_observed_low_ndvi_pixel():
    ctx = {"ndvi_max": np.full((40, 40), np.nan), "ndvi_n": np.zeros((40, 40), dtype="uint8")}
    ctx["ndvi_max"][0, 0], ctx["ndvi_n"][0, 0] = .3, 2
    ctx["ndvi_max"][0, 20], ctx["ndvi_n"][0, 20] = .2, 1
    ctx["ndvi_max"][20, 0], ctx["ndvi_n"][20, 0] = .3001, 2
    np.testing.assert_equal(modis.celdas_elegibles(ctx, ["2025-01", "2025-07"], .3), [[True, False], [False, False]])


def test_sampling_edges_and_threshold_quantization(monkeypatch):
    monkeypatch.setattr(modis, "FORMA", (2, 4))
    monkeypatch.setattr(modis, "PASO", 90)
    ctx = {k: np.arange(8, dtype="float32").reshape(2, 4) for k in modis.CONTEOS}
    ctx.update({k: np.full((2, 4), 2) for k in modis.CONTEOS.values()})
    ctx["contexto_id"] = "test"
    ctx["ndvi_max"][0, 0] = np.float32(.3)
    assert modis.muestrear(ctx, 90, -180)["ndvi_max"] == .3
    assert modis.muestrear(ctx, -90, 180)["ndvi_max"] == 7
    ctx["ndvi_max"][0, 0] = .3001
    assert modis.muestrear(ctx, 90, -180)["ndvi_max"] > .3
    ctx["ndvi_max"][0, 0] = np.nan
    assert modis.muestrear(ctx, 90, -180)["ndvi_max"] is None
    for lat, lon in [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0), (0, float("inf"))]:
        with pytest.raises(ValueError):
            modis.muestrear(ctx, lat, lon)


@pytest.mark.parametrize("meses", [[], ["2025-07", "2025-01"], ["2025-01", "2025-01"], ["2025-13"], ["../x"]])
def test_cache_rejects_invalid_months(meses):
    with pytest.raises(ValueError):
        modis.ruta_cache(Path("."), meses)


def test_download_strips_auth_on_redirect_and_publishes_only_hdf(tmp_path, monkeypatch):
    def responder(request):
        if request.url.host == "data.lpdaac.earthdatacloud.nasa.gov":
            assert request.headers["Authorization"] == "Bearer secreto-prueba"
            return httpx.Response(302, headers={"Location": "https://almacen.example/granulo?firma=privada"})
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"\x0e\x03\x13\x01test")
    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        monkeypatch.setattr(modis.httpx, "stream", client.stream)
        archivo = modis.descargar("https://data.lpdaac.earthdatacloud.nasa.gov/granulo.hdf", tmp_path, "secreto-prueba")
        assert archivo.read_bytes().startswith(b"\x0e\x03\x13\x01")
        assert not list(tmp_path.glob("*.part"))
        with pytest.raises(ValueError, match="HTTPS"):
            modis.descargar("https://otro.example/x.hdf", tmp_path, "secreto-prueba")


def test_download_rejects_html_and_cleans_up(tmp_path, monkeypatch):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>login</html>"))) as client:
        monkeypatch.setattr(modis.httpx, "stream", client.stream)
        with pytest.raises(ValueError, match="no es HDF4"):
            modis.descargar("https://data.lpdaac.earthdatacloud.nasa.gov/x.hdf", tmp_path, "token")
    assert not list(tmp_path.iterdir())


def test_hdf_cache_preparation_roundtrip_and_quality(tmp_path, monkeypatch):
    from pyhdf.SD import SD, SDC

    monkeypatch.setattr(modis, "FORMA", (1, 2))
    monkeypatch.setattr(modis, "granulo", lambda p, m: f"https://data.lpdaac.earthdatacloud.nasa.gov/{p}.{m}.hdf")
    meses = ["2025-01", "2025-07"]
    for mes in meses:
        for producto in modis.CAPAS:
            f = SD(str(tmp_path / f"{producto}.{mes}.hdf"), SDC.WRITE | SDC.CREATE)
            for sds, _ in modis.CAPAS[producto]:
                ds = f.create(sds, SDC.INT16 if producto == "MOD13C2" else SDC.UINT16, (1, 2))
                ds[:] = np.array([[3000, -3000]], dtype="int16") if producto == "MOD13C2" else np.array([[15000, 0]], dtype="uint16")
                ds.valid_range = [-2000, 10000] if producto == "MOD13C2" else [7500, 65535]
                ds.attr("_FillValue").set(SDC.INT16 if producto == "MOD13C2" else SDC.UINT16,
                                           -3000 if producto == "MOD13C2" else 0)
                ds.scale_factor = 10000.0 if producto == "MOD13C2" else .02
                ds.endaccess()
            quality = ({"CMG 0.05 Deg Monthly VI Quality": (SDC.UINT16, [1 << 11, 65535]),
                        "CMG 0.05 Deg Monthly pixel reliability": (SDC.INT8, [0, -1])}
                       if producto == "MOD13C2" else {"QC_Day": (SDC.UINT8, [0, 2]), "QC_Night": (SDC.UINT8, [0, 2])})
            for name, (tipo, valores) in quality.items():
                ds = f.create(name, tipo, (1, 2))
                ds[:] = np.array([valores], dtype={SDC.UINT16: "uint16", SDC.INT8: "int8", SDC.UINT8: "uint8"}[tipo])
                ds.endaccess()
            f.end()
    p = modis.preparar(tmp_path, meses, "")
    ctx = modis.cargar(p, meses)
    assert ctx["ndvi_n"].tolist() == [[2, 0]]
    np.testing.assert_allclose(ctx["ndvi_max"], [[.3, np.nan]], equal_nan=True)
    assert len(ctx["metadata"]["fuentes"]) == 4
    assert all(len(f["sha256"]) == 64 for f in ctx["metadata"]["fuentes"])
    assert modis.preparar(tmp_path, meses, "") == p
    with pytest.raises(ValueError):
        modis.cargar(p, ["2025-02"])
    # Una caché anterior sin QA nunca pasa por la nueva ruta.
    assert p.name.startswith(modis.VERSION)
    assert ctx["contexto_id"] == modis.identidad(json.loads(str(np.load(p)["metadata"])))
