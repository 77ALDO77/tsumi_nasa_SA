# Proyecto de análogos terrestres

[Contexto del reto](CONTEXTO_RETO.md) · [Plan](PLAN_HACKATHON.md) · [Flujo de trabajo](FLUJO_TRABAJO.md)

La implementación y los resultados de extracción están en [scrapping/](scrapping/README.md). Consulta el [diagnóstico y análisis de fuentes](scrapping/docs/ANALISIS_RESULTADOS.md).

Desde la raíz, con `.venv` activada:

```powershell
python -m scrapping --ca-bundle scrapping/certs/csa-verified-chain.pem
```

El bundle es local a este equipo; las instrucciones para regenerarlo están en el README de `scrapping`.
