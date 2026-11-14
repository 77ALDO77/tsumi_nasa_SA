# Variables del prototipo: contraste y propuesta de alcance

Estado: **recomendación pendiente de prueba con muestras**, 14 de noviembre de 2026. No cambia las cinco dimensiones de investigación por requisitos oficiales. Ninguna pareja de productos físicos se ha abierto y procesado todavía.

Ampliación: [temperatura, indicadores ambientales y evaluación de Earth2Studio](TEMPERATURA_EARTH2STUDIO.md). Se propone añadir temperatura superficial y contraste entre horarios al prototipo, con contexto meteorológico terrestre y fuentes planetarias propias. La integración está pendiente de prueba con datos.

## Qué estaba definido y qué demuestra la información nueva

[CONTEXTO_RETO.md](../CONTEXTO_RETO.md) propone suelo, minerales, polvo, hielo y permafrost como dimensiones candidatas. También contempla relieve y operaciones. El [plan](../PLAN_HACKATHON.md) exige una comparación real, una referencia delimitada, un candidato y un control; reserva el segundo cuerpo planetario como P2.

El [corpus consolidado](../scrapping/docs/SEGUNDA_PASADA.md) aporta 11 fuentes con texto y 27 pasajes candidatos. Eso es evidencia documental, no 11 datasets medidos. University Valley tiene el resultado documental cuantitativo más concreto del corpus. Elegirlo como MVP sigue condicionado a obtener observaciones planetarias comparables.

| Dimensión inicial | Variable que habría que medir | Evidencia nueva y consecuencia |
|---|---|---|
| Suelo/material superficial | Granulometría, densidad aparente o resistencia, según el ensayo; unidad y profundidad de muestreo | El corpus no incluye una pareja de mediciones comparables. «Tipo de suelo» por sí solo no basta. Mantener P1 si se elige un ensayo de materiales. |
| Minerales | Fases identificadas o rasgos espectrales bajo un método compatible | PTAL quedó bloqueado en el editor; hay bibliotecas PDS para explorar, sin muestras procesadas. Línea alternativa P1, no composición inferida por color. |
| Polvo | Tamaño de partículas, flujo, deposición o adherencia; elegir un proceso | Mojave documenta remolinos terrestres y extrapolación a Marte. No ofrece un mecanismo atmosférico transferible a la Luna. Dejar como perfil específico marciano. |
| Hielo | Profundidad hasta hielo, método de detección y escala | University Valley reporta 0–98 cm, sin datos individuales descargados. Es intervalo observado, no umbral de similitud. Mantener como perfil científico condicionado. |
| Permafrost | Temperatura del terreno por profundidad y duración, contenido de hielo por separado | El corpus no contiene series térmicas compatibles. No derivarlo de temperatura del aire, superficie o mera presencia de hielo. P2 para el MVP. |

La definición terrestre de permafrost se basa en terreno a 0 °C o menos durante al menos dos años consecutivos; no exige por definición un contenido particular de hielo. [International Permafrost Association](https://www.permafrost.org/what-is-permafrost/).

## Nueva información que cambia la decisión

- SWIM combina observaciones orbitales en mapas de consistencia de hielo de unos 3 km/píxel para rangos 0–1 m, 1–5 m y >5 m. No son mediciones puntuales de profundidad en centímetros ni probabilidades calibradas. Restar uno de esos valores a una profundidad terrestre daría una comparación inválida. [Artículo de SWIM, ficha USGS](https://www.usgs.gov/publications/refined-mapping-subsurface-water-ice-mars-support-future-missions).
- Hay productos de elevación para los tres cuerpos: NASADEM o Copernicus DEM en la Tierra; LOLA GDR en la Luna; MOLA o HRSC/MOLA en Marte. Esto hace razonable probar un mismo procesamiento topográfico. La consulta de documentación no confirma aún su descarga y lectura. [NASADEM](https://data.nasa.gov/dataset/nasadem-merged-dem-global-1-arc-second-v001), [LOLA y sus formatos](https://pds-geosciences.wustl.edu/missions/lro/lola_faq.htm), [productos marcianos USGS](https://fdp.astrogeology.usgs.gov/fdp/mars/).
- JETT3 documenta terreno, geología, comunicaciones y condiciones de iluminación simuladas. Sustenta una selección en función del objetivo de ensayo; no proporciona un ranking universal. [Noticia NASA](https://www.nasa.gov/humans-in-space/nasa-to-practice-artemis-moonwalking-roving-operations-in-arizona-desert/).

## Recomendación del prototipo

**Probar primero la preselección de terrenos terrestres con geometría regional similar a una zona lunar o marciana, para preparar ensayos de exploración.** Esta es una analogía topográfica/operativa con alcance explícito. Su utilidad para un equipo usuario todavía necesita validación. Mantener hielo y materiales como perfiles alternativos de investigación, sin mezclarlos en una puntuación general.

Se revisa la preferencia previa por University Valley porque fortaleza de un antecedente documental y factibilidad de una comparación reproducible son preguntas distintas. No se invalida ese estudio: la nueva comparación con SWIM muestra una dificultad de escala y tipo de variable que falta resolver.

| Prioridad | Variable | Métrica propuesta y unidad | Función |
|---|---|---|---|
| P0 | Pendiente regional | Distribución de pendientes; mediana y percentil 90 en grados | Comparar la inclinación del terreno a una misma escala física. |
| P0 | Relieve local | P95 de elevación menos P5 dentro de una ventana de tamaño fijo, en metros | Comparar la amplitud vertical, independientemente del nivel de referencia de cada planeta. |
| P1 | Irregularidad topográfica | RMS de residuos tras ajustar un plano local, en metros, a una ventana fija | Caracterizar variación residual si añade información a pendiente/relieve. No equivale a rugosidad de granos o bloques. |
| P1 | Material geológico documentado | Categoría o fase con técnica y fuente explícitas | Explicar por qué dos superficies geométricamente parecidas pueden servir para ensayos diferentes. |

Pendiente, relieve e irregularidad están relacionados: no tratarlos como tres evidencias independientes ni asignarles pesos arbitrarios que cuenten varias veces la misma propiedad. No usar altitud absoluta como similitud entre cuerpos: sus datums y significado ambiental son diferentes.

Temperatura, iluminación, polvo, hielo y minerales pasan a ser variables dependientes de un perfil concreto. Por ejemplo: un perfil térmico podría comparar temperatura superficial y amplitud de ciclo cuando estén disponibles a horarios y escalas compatibles; eso no acredita presencia de hielo. Un perfil mineralógico necesitaría datos espectrales o composicionales, no solo imágenes RGB.

Para mineralogía, fuentes de exploración adicionales: [biblioteca espectral PDS](https://pds-geosciences.wustl.edu/spectrallibrary/), [CRISM Type Spectra](https://crismtypespectra.rsl.wustl.edu/), [Moon Mineralogy Mapper, JPL](https://microdevices.jpl.nasa.gov/capabilities/imaging-spectroscopy/moon-mineralogy/). No se han descargado ni comprobado pares de espectros.

## Condiciones que impiden una comparación engañosa

1. Seleccionar una región planetaria y recortes terrestres del mismo tamaño físico; documentar el propósito del ensayo.
2. Usar metros y proyecciones/geometrías adecuadas al radio de cada cuerpo. Leer escalas, offsets, datums y valores ausentes de cada producto.
3. Filtrar y degradar los datos más finos a una escala común sustentada por el producto menos detallado. Igualar el tamaño de píxel por interpolación no iguala la resolución efectiva.
4. Fijar tamaño de ventana y método antes de ordenar candidatos; comprobar sensibilidad a otro tamaño de ventana y otra escala.
5. Conservar máscara válida, fracción de datos ausentes, cobertura, fuente, versión, fecha y exactitud disponible. Evidencia insuficiente no debe convertirse en cero de similitud.
6. Mostrar diferencias por variable y un control. Si se usa un índice agregado después, justificar sus tolerancias y pesos por el ensayo, sin llamarlo «porcentaje de analogía NASA».

HRSC/MOLA tiene un producto global de 200 m/píxel en el inventario USGS. Usarlo limita el análisis al relieve regional: no resuelve rocas, grietas ni peligros a escala de ruedas. La elección de otro producto puede cambiar ese alcance. [Inventario USGS](https://fdp.astrogeology.usgs.gov/fdp/mars/).

NASADEM cubre de 60° N a 56° S: deja fuera Antártida, Haughton y los sitios islandeses. Por tanto no puede ser la única fuente para los siete antecedentes. [Cobertura NASADEM](https://data.nasa.gov/dataset/nasadem-merged-dem-global-1-arc-second-v001).

Copernicus DEM ofrece productos globales GLO-30 y GLO-90, pero es un modelo de superficie que incluye vegetación e infraestructura. Hay que comprobar el recorte real y limitar o controlar esos efectos al compararlo con terreno planetario. [Documentación de Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).

## Siguiente prueba antes de fijar el alcance

P0: abrir un recorte terrestre y uno lunar **o** marciano, calcular pendiente y relieve con el mismo soporte físico y compararlos con un control. Elegir candidatos entre sublugares delimitados de los siete antecedentes; el nombre «Atacama» o «Antártida» no representa una única superficie. Extender el segundo cuerpo solo cuando el primer caso sea reproducible.

Si falla el acceso, faltan datos válidos o las métricas no aportan una decisión útil, reevaluar el perfil de hielo o materiales con una pareja concreta. La recomendación topográfica queda condicionada a esta prueba: todavía no se declara implementada ni validada.
