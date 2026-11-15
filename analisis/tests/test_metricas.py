import numpy as np

from analisis.fuentes import teselas_glo30
from analisis.metricas import metricas, pendiente_grados


def plane(deg, n=50, res=60.0):
    cols = np.arange(n) * res
    return np.tile(cols * np.tan(np.radians(deg)), (n, 1))


def test_inclined_plane_gives_its_slope():
    z = plane(10)
    slope = pendiente_grados(z, 60.0)
    assert abs(np.nanmedian(slope) - 10) < 0.1
    result = metricas(z, 60.0, 0.9)
    assert abs(result["pendiente_mediana_grados"] - 10) < 0.1
    assert result["rugosidad_rms_plano_m"] < 1e-6


def test_relief_is_p95_minus_p5():
    z = plane(10)
    p5, p95 = np.percentile(z, [5, 95])
    assert abs(metricas(z, 60.0, 0.9)["relieve_p95_p5_m"] - (p95 - p5)) < 0.01


def test_missing_values_are_not_zero():
    z = plane(10)
    z[:, :30] = np.nan
    result = metricas(z, 60.0, 0.9)
    assert result["estado"] == "evidencia_insuficiente"
    z = plane(10)
    z[0, 0] = np.nan
    assert abs(metricas(z, 60.0, 0.9)["pendiente_mediana_grados"] - 10) < 0.1


def test_glo30_tile_names_cover_window_across_tiles():
    names = list(teselas_glo30(35.0, -111.0, 15000))
    assert any("N34_00_W112_00" in n for n in names) and any("N35_00_W111_00" in n for n in names)
    assert all(n.startswith("https://copernicus-dem-30m.s3.amazonaws.com/") for n in names)


def test_only_404_counts_as_missing_tile():
    from rasterio.errors import RasterioIOError

    from analisis.fuentes import tesela_inexistente

    assert tesela_inexistente(RasterioIOError("HTTP response code: 404"))
    assert not tesela_inexistente(RasterioIOError("Read failed. See previous exception for details."))
    assert not tesela_inexistente(RasterioIOError("HTTP response code: 503"))
