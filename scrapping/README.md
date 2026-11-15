# Scraping documental del reto NASA

Código, pruebas, dependencias, inventario, resultados y análisis están en esta carpeta. El alcance científico se toma de [CONTEXTO_RETO.md](../CONTEXTO_RETO.md) y las URLs de [resources.txt](../resources.txt), [inputs/extraccion_fuentes.json](inputs/extraccion_fuentes.json) y los enlaces directos del contexto.

**Última revisión: 17 fuentes; 11 con texto, 6 con limitaciones; 27 pasajes candidatos y 293 enlaces.** [Diagnóstico y análisis científico](docs/ANALISIS_RESULTADOS.md) · [Auditoría JSON](docs/analisis_fuentes.json) · [Tabla CSV](docs/analisis_fuentes.csv).

Validación: 30 pruebas aprobadas, dependencias compatibles y reproducción idéntica de documentos, pasajes y cobertura desde esta ubicación.

**Etiquetas de análogos NASA (2026-11-15).** [inputs/analogos_nasa.json](inputs/analogos_nasa.json) añade los artículos de campo de NASA enlazados desde Analog Explorer. Las 6 fuentes se extrajeron en `scrapping/data/analogos-nasa`. Después se reprocesaron sin red en `analogos-nasa-revisado`, una vez que el extractor ya recogía los paneles «Image Details» de Analog Explorer. [inputs/etiquetas_analogos.json](inputs/etiquetas_analogos.json) define 22 etiquetas, que se pueden revisar a mano: sitio, cuerpo, dimensión (vocabulario cerrado), relación, expectativa del equipo y medibilidad con el analizador de relieve. `python -m scrapping.tools.prepare_analog_labels` comprueba el literal y el SHA256 de cada una y escribe [docs/etiquetas_analogos.json](docs/etiquetas_analogos.json). La revisión humana se anota en la entrada (`revision_humana`, `revisor`, `fecha_revision`) y la herramienta la conserva; hoy las 22 están pendientes.

```powershell
python -m scrapping --inventory scrapping/inputs/analogos_nasa.json --source "San Francisco Volcanic Field, Arizona" --source "Islandia" --source "Valley of Ten Thousand Smokes, Alaska" --source "NASA Analog Missions" --source "NASA Analog Explorer" --source "Caso NASA JETT3" --output scrapping/data/<carpeta-nueva>
python -m scrapping.tools.prepare_analog_labels
```

[Segunda pasada consolidada y preparación del MVP 0](docs/SEGUNDA_PASADA.md): usa la descarga reciente y recupera Mojave desde su copia completa anterior. Incluye cinco registros documentales con trazabilidad y revisión humana pendiente.

## Ejecutar desde la raíz del proyecto

Con el entorno que ya tienes activado, el comando actualizado es:

```powershell
python -m scrapping --ca-bundle scrapping/certs/csa-verified-chain.pem
```

El PEM local ya fue generado y probado para CSA. No se distribuye con Git. Sin ese parámetro el cliente utiliza su configuración normal de certificados, que en este equipo falla para CSA.

```powershell
# Inventario sin solicitudes de red
python -m scrapping --list

# Solo fuentes seleccionadas; --source admite nombres exactos o IDs y es repetible
python -m scrapping --source Diviner --source LRO

# Tiempo, reintentos y carpeta NUEVA; no sobrescribe ejecuciones existentes
python -m scrapping --output scrapping/data/mi-ejecucion --timeout 60 --attempts 2 --delay 1 --ca-bundle scrapping/certs/csa-verified-chain.pem

# Reprocesar respuestas locales, sin red
python -m scrapping --offline scrapping/data/resultado-revisado --output scrapping/data/mi-reproduccion

# Consolidar una descarga general y reintentos; la última respuesta prevalece por fuente
python -m scrapping --offline scrapping/data/20261114T163415819391Z --offline scrapping/data/revision-nueva-red --offline scrapping/data/csa-cadena-verificada --output scrapping/data/mi-consolidacion

# Auditar contenido extraído, sin red
python -m scrapping.nasa_scraper.analysis --run scrapping/data/resultado-revisado --baseline scrapping/data/20261114T163415819391Z

# Pruebas sin red
python -m pytest -q scrapping/tests
```

Si no activaste el entorno, sustituye `python` por `.\.venv\Scripts\python.exe`. El antiguo `python -m nasa_scraper` desde la raíz deja de aplicar porque el paquete fue trasladado.

Código de salida `0`: todas las fuentes seleccionadas entregaron texto suficiente. `2`: resultado parcial o argumento inválido; consultar el mensaje y el manifest. No se considera éxito científico que una página tenga texto. JAXA permanece como `portal_navegacion` y no incrementa la cuenta `extraido`.

## Instalación y certificados

Python >=3.10; verificado con Python 3.13.5 en Windows. La `.venv` existente se mantiene en la raíz para no romper el entorno activado. No se necesitan claves, variables de entorno ni navegadores instalados.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scrapping/requirements-dev.txt
```

`requirements.txt` contiene dependencias de ejecución; `requirements-dev.txt` añade pytest. `requirements-lock.txt` conserva las versiones del entorno Windows/Python 3.13 probado. Scrapling instala dependencias de fetchers, pero este programa utiliza HTTP y selectores; no ejecuta Chromium.

Para regenerar el bundle de CSA en este equipo Windows:

```powershell
python -m scrapping.tools.export_windows_ca
powershell -NoProfile -File scrapping/tools/export_csa_chain.ps1
python -m scrapping --source RCM --source RADARSAT-1 --ca-bundle scrapping/certs/csa-verified-chain.pem
```

El primer paso exporta certificados públicos ya confiados por Windows junto con certifi. El segundo obtiene la cadena de CSA mediante `SslStream` con validación predeterminada y exige que `X509Chain.Build` tenga éxito. Añade emisores, no convierte el certificado hoja del sitio en autoridad de confianza. No modifica el almacén del sistema ni usa `verify=False`. Si Windows no valida, el script se detiene. Los archivos PEM y JSON de procedencia quedan en `scrapping/certs/`, excluida de Git. No son portables como configuración de confianza de otros equipos; allí debe usarse un bundle local validado.

## Estructura

```text
scrapping/
  __main__.py                    Entrada: python -m scrapping
  nasa_scraper/
    sources.py                   Inventario, URLs e IDs estables
    transport.py                 Scrapling, TLS, robots y límites HTTP
    extraction.py                Texto HTML/PDF y muestreo de pasajes
    pipeline.py                  Archivos, hashes, deduplicación y reportes
    analysis.py                  Auditoría cuantitativa de ejecuciones
  inputs/extraccion_fuentes.json Inventario histórico, contenido conservado
  tests/                         Pruebas deterministas
  tools/                         Exportación local de certificados verificados
  certs/                         Certificados públicos locales, excluidos de Git
  docs/                          Diagnóstico, análisis y validación histórica
  data/<ejecucion>/               Copias, documentos y resultados, excluidos de Git
  requirements*.txt              Dependencias
```

`--inventory`, `--context` y `--resources` permiten usar otras entradas. Los valores predeterminados se resuelven desde los archivos del proyecto. Los antecedentes del inventario se guardan como `contexto_previo_no_validado`; no se presentan como resultados recién obtenidos. Las páginas y documentos se tratan como datos, nunca como instrucciones ejecutables.

## Salidas

- `sources.json` y `CONTEXTO_RETO.md`: entradas y alcance utilizados.
- `manifest.json`: estado por fuente, error, fase/URL/código cuando está disponible, HTTP, redirecciones, fecha UTC, bytes y SHA256. `completo` indica que terminó el recorrido, no que todas las fuentes funcionaron.
- `robots.json`: política consultada y muestra de respuestas no interpretables. Se guarda junto con el checkpoint después de cada fuente.
- `raw/<source_id>.bin`: cuerpo recibido para auditoría y reproducción, incluso errores HTTP.
- `documents/<source_id>.json`: título, autor/fecha declarados, segmentos, encabezados, XPath o página PDF, enlaces y páginas sin texto.
- `evidencia.jsonl`: hasta 20 ventanas de 600 caracteres por fuente. Se recorre todo el documento y se distribuye la muestra, conservando menciones de sitios cuando caben. No es extracción exhaustiva.
- `cobertura.csv`: las 35 combinaciones de siete sitios y cinco dimensiones; registra coocurrencias en los pasajes exportados. No encontrar una palabra no demuestra ausencia científica.
- `resumen.md`: estados y número de pasajes por fuente.
- `analisis.json/.csv`: auditoría opcional generada con el módulo `analysis`.

Las filas de tablas HTML quedan como texto. El programa no infiere unidades, umbrales, incertidumbre ni medidas: esos campos permanecen en `null` y la revisión humana, pendiente. Los encabezados no generan pasajes por sí solos. Tener cero pasajes de las cinco dimensiones tampoco vuelve inútil una fuente: JETT3 aporta contexto operativo y Diviner documenta temperaturas y valores ausentes.

## Límites y recuperación

Una solicitud a la vez; intervalo mínimo por origen de un segundo y respeto de `Crawl-delay`/`Request-rate`. Hasta dos intentos, cinco redirecciones y 25 MiB descomprimidos por respuesta. Los destinos de redirección vuelven a comprobar robots. Se respeta `Retry-After`: si pide más de 30 segundos, se registra el fallo sin reintento inmediato.

El agente es `AnalogEvidenceBot/0.1`; TLS se mantiene activo. No se fuerza autenticación, CAPTCHA ni HTTP 403. Robots ausente con 404/410 permite consultar; 401/403 excluye. Una respuesta HTML o un fallo de consulta se trata conservadoramente como acceso no resuelto; no equivale a una prohibición explícita del proveedor.

| Estado | Interpretación / siguiente acción |
|---|---|
| `error_tls` | Revisar el emisor/cadena/almacén de confianza. Usar un PEM validado con `--ca-bundle`. |
| `timeout`, `error_red` | Fallo de conexión, DNS o tiempo; revisar diagnóstico y repetir solo la fuente afectada. |
| `requiere_javascript_o_api` | La aplicación no entrega contenido útil con HTTP estático; usar un acceso oficial adecuado. |
| `robots_no_disponible` | Política no interpretable; revisar `robots.json` antes de elegir otra vía oficial. |
| `excluido_por_robots`, `bloqueo_acceso` | Respetar la exclusión/restricción y buscar una fuente autorizada. |
| `portal_navegacion` | Índice de enlaces recuperado, sin documento científico suficiente. |
| `pdf_sin_texto_requiere_ocr`, `contenido_insuficiente` | Inspección del original; OCR o selector específico si corresponde. |
| `integridad_invalida` | La copia local ya no coincide con su SHA256; no es una reproducción válida. |
| `limite_tamano` | Elegir una muestra/documento menor; no es un descargador de productos voluminosos. |

Los enlaces se exportan, no se recorren automáticamente. No se adquieren rásteres, escenas, espectros ni productos autenticados. La reproducción offline verifica hashes y conserva la fecha de consulta original. Para las fuentes sin cuerpo local conserva el diagnóstico anterior y marca `sin_cuerpo_local`; no vuelve a comprobar su disponibilidad.

La migración conservó las ejecuciones históricas. Sus referencias textuales a `data/scraping` son procedencia histórica; los archivos físicos están ahora en `scrapping/data` y pueden reprocesarse desde allí.

Referencias: [Scrapling, BSD-3-Clause](https://github.com/d4vinci/Scrapling) · [API HTTP](https://scrapling.readthedocs.io/en/latest/fetching/static.html). Siguiente etapa científica: revisar pasajes y abrir muestras terrestres/planetarias compatibles, según [FLUJO_TRABAJO.md](../FLUJO_TRABAJO.md).
