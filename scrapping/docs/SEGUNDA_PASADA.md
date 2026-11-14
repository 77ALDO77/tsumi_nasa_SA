# Segunda pasada: consolidación y preparación de evidencia

## Resultado

La ejecución `20261114T165308716396Z` obtuvo texto de 10 fuentes, con 7 fragmentos candidatos. Mojave falló por timeout durante los dos intentos de 60 segundos. Se consolidó esta ejecución con la descarga completa anterior de Mojave (`mojave-verificado`), sin nuevas solicitudes de red.

El [corpus consolidado](../data/segunda-pasada-consolidada/resumen.md) contiene **17 fuentes: 11 con texto extraído y 6 con limitaciones; 27 fragmentos candidatos y 293 enlaces**. La consolidación no acredita que Mojave haya vuelto a estar disponible en línea. Su fecha de consulta y origen anterior se conservan en el [manifest](../data/segunda-pasada-consolidada/manifest.json).

[Auditoría JSON](../data/segunda-pasada-consolidada/analisis.json) · [Tabla de auditoría](../data/segunda-pasada-consolidada/analisis.csv) · [Cinco registros documentales preparados](evidencia_segunda_pasada.json)

## Estado de acceso

| Fuente | Estado de la segunda pasada | Decisión |
|---|---|---|
| CSA: RCM y RADARSAT-1 | Extraídas con el bundle de certificados validado | Acceso documental resuelto; adquisición de escenas pendiente. |
| Mojave | Timeout en la descarga reciente | Reutilizar los 21.427.864 bytes de la copia completa, comprobando SHA256. |
| Earthdata | Requiere JavaScript/API | Seleccionar un producto y usar su servicio oficial cuando se defina la variable. |
| Worldview y catálogo ESA | Robots respondió HTML | Mantener el diagnóstico anterior; la consolidación offline no vuelve a comprobar acceso. |
| JAXA | Portal de navegación | Conservar enlaces para elegir un servicio/producto; no contarlo como estudio. |
| Yungay y PTAL | HTTP 403 del editor | Solo buscar copia autorizada si esa línea científica es necesaria. |

Los seis casos limitados corresponden a Earthdata, Worldview, ESA, JAXA, Yungay y PTAL. No es necesario resolver todos para demostrar un caso científico acotado.

## Evidencia preparada

Los siguientes registros fueron contrastados por el asistente con el texto local. Cada registro del JSON conserva la frase literal, XPath, URL, fecha de consulta, SHA256 y límite de interpretación. **La revisión humana del equipo permanece pendiente.**

| ID | Resultado documental | Uso permitido y límite |
|---|---|---|
| `UV-N-01` | El resumen declara 475 mediciones en cuatro valles. | Describir el alcance de la campaña; no atribuir las 475 solo a University Valley. |
| `UV-DEPTH-01` | Profundidad hasta terreno cementado por hielo de 0–98 cm en University Valley. | Intervalo terrestre reportado; no es un umbral de selección ni una observación en Marte. |
| `UV-GRADIENT-01` | Tendencia de 32 cm de profundidad por kilómetro a lo largo del valle. | Describir la variación espacial reportada; incertidumbre y método completo todavía faltan. |
| `DIVINER-NODATA-01` | La nota RDR indica `-9999` para `tb` ausente, columna 24. | Preparar una regla de limpieza, que debe verificarse con la etiqueta y versión del producto elegido. |
| `JETT-SIM-01` | La noticia anuncia caminatas nocturnas con un sol simulado. | Distinguir configuración del ensayo y ambiente natural; no acredita el resultado de ese ensayo. |

Mojave se conserva como antecedente metodológico, sin incorporar cifras nuevas desde su PDF: la capa de texto contiene errores y hay seis páginas sin texto extraíble. Las cantidades del PDF necesitan revisión visual antes de pasar a una comparación.

PDS, LRO, Diviner, Copernicus, CSA y el tutorial SAR facilitan descubrir o utilizar productos. La cuenta de fuentes recuperadas no mide cuántas observaciones tenemos. JETT3 aporta contexto operativo aunque no produzca coincidencias con las cinco dimensiones del filtro.

## Preparación del MVP 0

La línea provisional mejor sustentada documentalmente en este corpus es **profundidad hasta terreno cementado por hielo en University Valley**. Su aceptación como caso de MVP depende de conseguir mediciones planetarias de la misma propiedad y método comparable. No se ha seleccionado un lugar marciano ni verificado su producto.

| P0 pendiente | Condición verificable para avanzar |
|---|---|
| Muestra terrestre | Obtener datos o una tabla del estudio con ubicación, método, profundidad y unidades. El intervalo del resumen solo no permite reproducir una distribución. |
| Muestra planetaria | Abrir observaciones de profundidad a hielo con ubicación, método y unidades. La temperatura superficial de Diviner no sustituye esa profundidad. |
| Comparabilidad | Documentar qué significa «cementado por hielo» en cada estudio, escala, límite de detección e incertidumbre disponible. |
| Control | Delimitar otra zona o muestra que permita interpretar una diferencia; su selección sigue pendiente. |
| Cálculo | Reproducir una diferencia en unidades físicas usando ambas muestras; registrar faltantes y supuestos. |

Si no se obtiene una pareja comparable en la ventana de viabilidad del plan, reducir o cambiar la pregunta. No deducir presencia de hielo de temperatura favorable ni permafrost de la sola presencia de hielo. No iniciar un ranking con los intervalos documentales como si fueran umbrales universales.

## Reproducción desde la raíz

La carpeta de salida debe ser nueva:

```powershell
python -m scrapping --offline scrapping/data/20261114T165308716396Z --offline scrapping/data/mojave-verificado --output scrapping/data/otra-segunda-pasada
python -m scrapping.nasa_scraper.analysis --run scrapping/data/otra-segunda-pasada --baseline scrapping/data/20261114T165308716396Z
```

Los cinco registros preparados se regeneran contra el corpus guardado con:

```powershell
python -m scrapping.tools.prepare_second_pass
```

Este comando comprueba que cada frase exista en un único segmento y que los bytes de su fuente coincidan con el SHA256. Esa comprobación garantiza trazabilidad textual; no reproduce el estudio ni sustituye su revisión científica.

Las ejecuciones originales se conservan. `scrapping/data/` continúa excluida de Git; el JSON de evidencia preparada y este informe están en `scrapping/docs/`, fuera de esa exclusión. Para que los documentos locales enlazados acompañen una entrega, también hay que conservar el corpus.

Validación realizada: SHA256 de todos los cuerpos del consolidado comprobados; para las fuentes distintas de Mojave se verificó que el hash coincida con la segunda pasada. Otra ejecución offline reprodujo exactamente los 13 documentos JSON, la evidencia JSONL y la cobertura CSV (15 archivos). Los cinco fragmentos preparados coinciden literalmente con sus segmentos fuente.
