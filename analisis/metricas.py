"""Métricas de relieve de docs/VARIABLES_PROTOTIPO.md sobre una malla métrica.

Los NaN son datos ausentes: nunca se convierten en cero y se propagan a la pendiente.
"""
import numpy as np

# Cambia esta cadena si cambia el cálculo: la base no reemplaza métricas de otra versión.
VERSION_METODO = "relieve-v2-aeqd-average-horn-ldec"

def pendiente_grados(z: np.ndarray, res_m: float) -> np.ndarray:
    """Pendiente de Horn (vecindad 3x3); una celda con algún vecino ausente queda en NaN."""
    p = np.pad(z.astype("float64"), 1, constant_values=np.nan)
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def metricas(z: np.ndarray, res_m: float, fraccion_valida_min: float) -> dict:
    valid = np.isfinite(z)
    slope = pendiente_grados(z, res_m)
    slope = slope[np.isfinite(slope)]
    base = {"n_celdas": int(z.size), "n_celdas_validas": int(valid.sum()),
            "fraccion_valida": round(float(valid.mean()), 4), "res_m": res_m}
    if valid.mean() < fraccion_valida_min or slope.size == 0:
        return {**base, "estado": "evidencia_insuficiente",
                "motivo": f"fracción válida {valid.mean():.3f} < {fraccion_valida_min}"}
    heights = z[valid]
    rows, cols = np.nonzero(valid)
    design = np.c_[cols * res_m, rows * res_m, np.ones(rows.size)]
    coef, *_ = np.linalg.lstsq(design, heights, rcond=None)
    residual = heights - design @ coef
    p5, p95 = np.percentile(heights, [5, 95])
    return {**base, "estado": "calculado",
            "pendiente_mediana_grados": round(float(np.median(slope)), 3),
            "pendiente_p90_grados": round(float(np.percentile(slope, 90)), 3),
            "relieve_p95_p5_m": round(float(p95 - p5), 2),
            "rugosidad_rms_plano_m": round(float(np.sqrt(np.mean(residual ** 2))), 2)}


def sombreado(z: np.ndarray, res_m: float, azimut=315.0, altura=45.0) -> np.ndarray:
    """Sombreado de relieve en uint8 para inspección visual; la iluminación es artificial."""
    dy, dx = np.gradient(np.nan_to_num(z, nan=float(np.nanmean(z))), res_m)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az, alt = np.radians(360 - azimut + 90), np.radians(altura)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    out = (np.clip(shade, 0, 1) * 255).astype("uint8")
    out[~np.isfinite(z)] = 0
    return out
