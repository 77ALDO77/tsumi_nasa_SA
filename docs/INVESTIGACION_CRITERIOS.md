# Investigación de criterios de selección de análogos

Estado: protocolo y hallazgos iniciales. Scraping automatizado implementado y probado; análisis documental inicial realizado, con revisión humana de los pasajes todavía pendiente. [Errores y utilidad de las fuentes](../scrapping/docs/ANALISIS_RESULTADOS.md). Actualización: 14 de noviembre de 2026.

## Propósito

Determinar cómo investigaciones y ensayos reales justifican la selección de sitios terrestres análogos. Extraer objetivos, criterios, métricas, restricciones y límites con trazabilidad. El enfoque topográfico del plan es provisional hasta completar esta revisión acotada.

## Distinciones obligatorias

- Análogo científico: útil para una pregunta o proceso particular.
- Análogo de operaciones: útil para probar procedimientos, equipos o interacción humana.
- Sitio viable para una campaña: además requiere condiciones de acceso, permisos, logística y seguridad.
- Sitio de aterrizaje o base extraterrestre: problema diferente; no transferir automáticamente sus requisitos a la selección terrestre.
- Criterio: característica relevante; métrica: forma de medirla; umbral: límite contextual; peso: importancia adoptada por un método. No son equivalentes.

No etiquetar un sitio como certificado, elegible o aprobado por NASA sin evidencia explícita de ese estatus y alcance. Ser utilizado en un estudio NASA tampoco implica certificación general.

## Fuentes iniciales y hallazgos

1. NASA, Planetary Analogs: https://science.nasa.gov/solar-system/planetary-analogs/
   - Contexto y categorías de uso. No proporciona por sí sola umbrales cuantitativos universales.
2. USGS, Terrestrial Analogs: https://www.usgs.gov/science/science-explorer/planetary-science/terrestrial-analogs
   - Vincula sitios y procesos con investigación, formación, pruebas y planificación de recorridos.
3. NASA, preparación JETT3 y D-RATS, 2022: https://www.nasa.gov/humans-in-space/nasa-to-practice-artemis-moonwalking-roving-operations-in-arizona-desert/
   - Terreno, geología y comunicaciones influyeron en el contexto del ensayo; se simularon condiciones de iluminación mediante equipos y trabajo nocturno.
4. Huff et al., cartografía para JETT5, resumen de congreso: https://ntrs.nasa.gov/citations/20230010127
   - Diversidad geológica, ambientes análogos y acceso; integración de imágenes, elevación y radar a escalas apropiadas para el ejercicio.
   - Es evidencia específica de una campaña; no una norma universal.
5. Informe técnico JETT3, 2023: https://ntrs.nasa.gov/api/citations/20230010686/downloads/EHP-20021_JETT3_Test_Report_Baseline_20230010686.pdf
   - Fuente para profundizar condiciones instrumentadas, configuración del ensayo y límites. Lectura integral pendiente.
6. Stern et al., 2025, JGR Planets: https://doi.org/10.1029/2024JE008803
   - Marco para evaluar análogos de mundos oceánicos respecto a preguntas científicas, mediciones, logística y limitaciones.
   - Aporta estructura metodológica; sus parámetros específicos de hielo o habitabilidad no deben trasladarse a Luna/Marte sin justificación.

## Papel del scraping

Objetivo: construir un corpus pequeño y auditable de evidencia, no buscar indiscriminadamente todo Internet ni fabricar un score con frecuencia de palabras.

Flujo:
1. Inventariar fuentes oficiales locales y referencias primarias pertinentes.
2. Preferir API, catálogo o descarga oficial cuando existan; usar extracción HTML/PDF para documentos y tablas.
3. Comprobar condiciones de acceso y robots antes de automatizar; no evadir autenticación ni restricciones.
4. Conservar URL, título, autor/institución, fecha, tipo de publicación y fecha de consulta.
5. Extraer fragmentos breves con sección o página y enlace al documento original.
6. Identificar objetivo del estudio, sitio, cuerpo planetario y criterio utilizado.
7. Separar dato reportado, interpretación del autor y nuestra inferencia.
8. Revisar manualmente cada criterio que llegue al algoritmo. La extracción automática no valida su significado.
9. Deduplicar versiones y limitar solicitudes; evitar recopilar contenido completo sin necesidad.
10. Descargar datos científicos mediante sus servicios oficiales; las páginas descriptivas no sustituyen los productos.

## Esquema de la matriz de evidencia

source_id, url, titulo, autor_institucion, fecha, tipo_fuente, pagina_seccion,
objetivo_estudio, sitio_terrestre, referencia_planetaria, tipo_analogia,
criterio, metrica, unidad, escala_espacial_temporal, valor_o_umbral,
alcance_del_umbral, metodo_medicion, dataset, incertidumbre,
restriccion_operativa, limitacion_analogia, estado_evidencia, revision_manual.

Valor desconocido = no reportado. No completar faltantes con estimaciones no identificadas.

## Familias a investigar; todavía no son métricas seleccionadas

- Terreno y morfología: pendiente, relieve, rugosidad a escala definida, distribución de obstáculos.
- Geología y materiales: litología, mineralogía, granulometría y propiedades mecánicas cuando estén medidas.
- Ambiente: temperatura de superficie, ciclos, geometría de iluminación, disponibilidad y estado del agua/hielo.
- Procesos: transporte de sedimentos, volcanismo, erosión, alteración, hielo; comparar mecanismos además de apariencia.
- Operaciones: dimensiones del área, comunicaciones, aislamiento y configuración de la prueba.
- Viabilidad de campo: acceso, permisos, protección ambiental, transporte, seguridad y estacionalidad.
- Calidad de evidencia: cobertura, resolución efectiva, precisión, fecha y comparabilidad del instrumento.

## Regla de decisión propuesta para el producto

Objetivo → condiciones indispensables → características comparables → datos disponibles → métricas → evaluación de candidatos → límites.

Separar tres salidas: correspondencia científica, viabilidad operativa y calidad de evidencia. Una carencia indispensable no debe quedar oculta mediante compensación de otras variables en una media ponderada. Un dato faltante será desconocido, no cero ni cumplimiento.

Estas reglas son nuestra propuesta metodológica, no un procedimiento oficial NASA.

## Entregable y límite temporal

Primera ventana de tres horas del plan: revisar aproximadamente 5–8 fuentes primarias pertinentes, con al menos un caso lunar y uno marciano si son accesibles. Es un objetivo de alcance, no un corpus ya completado.

Salida: matriz revisada, lista de criterios sustentados, huecos de datos y decisión de un caso de uso. Seleccionar 2–4 métricas implementables y justificadas; si las fuentes no respaldan una selección, reducir o cambiar el caso de uso. No ampliar indefinidamente la investigación.
