# Validación inicial del extractor documental

Registro histórico anterior a la revisión de la nueva red. Resultado vigente: [análisis de errores y fuentes](ANALISIS_RESULTADOS.md).

Fecha: 14 de noviembre de 2026. Python 3.13.5, Scrapling 0.5.1, pypdf 6.21.4. La verificación se realizó con solicitudes reales a las URLs del inventario y las referencias directas de `CONTEXTO_RETO.md`, además de pruebas deterministas locales.

## Resultado observado

17 URLs únicas: **9 con texto extraído y 8 con limitaciones explícitas**. El corpus consolidado contiene 32 fragmentos candidatos, 291 enlaces de documentos y una matriz de cobertura de 35 celdas. Ningún fragmento está validado científicamente. El número de enlaces no es el número de productos descargados.

| Fuentes | Resultado |
|---|---|
| PDS, LRO, Diviner, tutorial SAR de CSA, Copernicus, resumen de University Valley, informe de Mojave, JETT3 y Analog Explorer | Texto recuperado. El resumen de University Valley no implica acceso al artículo completo. |
| Earthdata Search | Interfaz que requiere JavaScript o acceso por API. |
| Worldview y ESA Open Science Catalogue | `robots.txt` respondió HTML; no se automatizó la descarga de sus portadas. |
| RCM y RADARSAT-1 | Fallo de validación de certificado TLS al consultar robots; no se desactivó TLS. |
| JAXA G-Portal | HTML recibido, con contenido insuficiente para el extractor de bloques; enlaces conservados. |
| Artículo de Yungay y PTAL | Redirecciones DOI resueltas; los editores respondieron HTTP 403. |

El informe de Mojave se recuperó en un reintento de mayor duración: 21.427.864 bytes, 123 páginas, 117 segmentos con texto. Las páginas PDF 88, 113, 114, 115, 116 y 117 no produjeron texto; requieren inspección visual y, si contienen información, extracción adicional. El scraper no hizo OCR.

Diviner conservó 38 segmentos y 24 enlaces tras excluir el menú lateral de su HTML con tablas de maquetación. La nota sobre `-9999` es localizable en el documento JSON mediante XPath. No se abrió ningún producto térmico ni se interpretó ese valor como una medición válida.

## Artefactos locales

- [Resumen consolidado](../data/resultado-final/resumen.md).
- [Manifest con hashes y estados por fuente](../data/resultado-final/manifest.json).
- [Pasajes candidatos](../data/resultado-final/evidencia.jsonl).
- [Cobertura de sitios y dimensiones](../data/resultado-final/cobertura.csv).

Los cuerpos originales, los registros HTTP y la copia del contexto usado están en esa carpeta. `scrapping/data/` está excluida de Git: estos enlaces requieren conservar la carpeta local. `scrapping/inputs/extraccion_fuentes.json` mantiene intacta la investigación previa.

La primera descarga general está en `scrapping/data/fuentes-verificadas`; el reintento de Mojave está en `scrapping/data/mojave-verificado`. El consolidado se generó sin red, tomando el reintento como respuesta posterior para esa fuente:

```powershell
.\.venv\Scripts\python.exe -m scrapping --offline scrapping/data/fuentes-verificadas --offline scrapping/data/mojave-verificado --output scrapping/data/otra-consolidacion
```

La carpeta de salida debe ser nueva. Las fechas de consulta pertenecen a las descargas originales, no a la reproducción.

## Comprobaciones

15 pruebas locales aprobadas: normalización/deduplicación de fuentes, contenido y localizadores HTML, exclusión de navegación LRO, páginas PDF y falta de texto, identificación de interfaces JavaScript/bloqueos, errores HTTP, robots en redirecciones, indisponibilidad de robots, integridad SHA256, reproducción offline, consolidación de reintentos, límite de tamaño y respeto de `Retry-After`.

`pip check`: sin incompatibilidades de dependencias. La extracción real confirma acceso a HTML y PDF; no confirma calidad de OCR, exactitud científica ni disponibilidad de productos físicos comparables.

Una segunda ejecución sin red en `scrapping/data/reproducibilidad-verificada` reprodujo exactamente los bytes de 13 archivos: 11 documentos JSON, `evidencia.jsonl` y `cobertura.csv`. Los 11 documentos incluyen las respuestas de Earthdata y JAXA que no cumplen el criterio de contenido suficiente; el total de fuentes con estado `extraido` sigue siendo 9.

Para el MVP 0 todavía falta revisar pasajes, elegir productos concretos y abrir una muestra terrestre y una planetaria con unidades y escalas compatibles.

