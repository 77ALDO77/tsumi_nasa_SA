# Temperatura e indicadores ambientales: evaluación de Earth2Studio

Estado: revisión de documentación y código fuente público, 14 de noviembre de 2026. **Earth2Studio no está instalado ni se ha ejecutado una descarga o un modelo.** La topografía tiene metodología propuesta; sus resultados tampoco deben declararse validados hasta completar la prueba con muestras.

## Decisión recomendada

Añadir una caracterización térmica de los candidatos y un contexto meteorológico terrestre. Evaluar Earth2Studio como adaptador opcional para datos históricos ERA5, sin incorporar pronósticos neuronales al núcleo del MVP. Para observaciones térmicas de superficie usar productos de Tierra, Luna y Marte con documentación propia.

La herramienta facilita acceso y procesamiento terrestre; no entrega por sí sola una comparación planetaria ni evidencia de minerales, polvo, hielo subsuperficial o permafrost. Sus modelos meteorológicos terrestres no quedan validados para Luna/Marte por cambiar las coordenadas o las unidades.

La elección anterior de pendiente y relieve se amplía con temperatura superficial. La distinción entre analogía científica, ensayo operativo y condiciones logísticas se mantiene: un sitio puede asemejarse topográficamente y ofrecer una coincidencia térmica parcial, con diferencias atmosféricas que limiten la transferencia del ensayo.

## Qué comprobamos en el repositorio

Earth2Studio es un marco para flujos de meteorología y clima con IA, con adaptadores de datos y modelos intercambiables. Consultamos el [repositorio](https://github.com/NVIDIA/earth2studio) y la [lista oficial de fuentes](https://nvidia.github.io/earth2studio/main/modules/datasources_analysis/).

El adaptador [ARCO_ERA5](https://raw.githubusercontent.com/NVIDIA/earth2studio/main/earth2studio/data/arco.py) devuelve reanálisis horario en una malla de 0,25°. Aproximadamente son 28 km de separación latitudinal; la separación longitudinal depende de la latitud. No resuelve el microclima de un sublugar pequeño. El reanálisis combina modelado y observaciones; no debe etiquetarse como medición instrumental puntual.

El [léxico de la versión 0.20.0](https://raw.githubusercontent.com/NVIDIA/earth2studio/0.20.0/earth2studio/lexicon/arco.py) declara los identificadores que se proponen abajo. Que una variable figure en el léxico no confirma la disponibilidad de todos sus tiempos en el almacén remoto: la primera descarga debe comprobarlo.

El adaptador consultado construye matrices globales por fecha y variable. Recortar después a una coordenada no evita haber solicitado campos globales. No solicitar años horarios completos con múltiples variables en una primera prueba. Para consultas pequeñas puede ser más simple acceder al dataset con recorte en origen usando otro cliente.

El repositorio advierte de cambios incompatibles después de 0.20.0. Una eventual prueba debe fijar versión y usar un entorno separado del scraper. La lectura de datos no implica ejecutar una red en GPU; las exigencias de inferencia dependen del modelo. La instalación base incorpora dependencias como PyTorch y herramientas de formatos meteorológicos: hay que comprobar compatibilidad y coste en este Windows/Python 3.13. [Dependencias actuales](https://github.com/NVIDIA/earth2studio/blob/main/pyproject.toml).

## Variables y función en el prototipo

| Prioridad | Variable | Fuente terrestre candidata | Métrica propuesta | Papel y límite |
|---|---|---|---|---|
| P0 | Temperatura de superficie | MODIS LST; `skt` de ERA5 como contexto modelado | Mediana y percentiles 5/95 de observaciones filtradas por hora solar y estación, en K | Caracterizar exposición térmica; distinguir observación y reanálisis. |
| P0 | Contraste térmico día/noche | Pares LST con horas conocidas; serie `skt` para contexto | Diferencia entre temperaturas a dos horarios definidos, en K | No llamarla amplitud diaria completa si solo hay dos muestras. |
| P0 | Cobertura y calidad | QA del producto, tiempos y máscaras | Número de muestras, porcentaje válido y cobertura de horarios/estaciones | Condición de comparabilidad, no rasgo físico de analogía. |
| P1 | Temperatura del aire | `t2m` | Mediana, extremos muestreados y horas dentro del intervalo del ensayo | Condiciones de campaña terrestre; no intercambiable con temperatura de superficie. |
| P1 | Precipitación | `tp` | Acumulación y frecuencia de precipitación en el periodo | Contexto terrestre. La precipitación sola no constituye un índice completo de aridez. |
| P1 | Humedad | `d2m` junto a `t2m` | Humedad relativa derivada con fórmula y convenciones documentadas | Contexto terrestre y condiciones del ensayo. |
| P1 | Viento | `u10m`, `v10m` | Velocidad resultante y percentiles | Condiciones de operación. Velocidad semejante no acredita transporte de polvo equivalente en Marte. |
| P1 | Presión superficial | `sp` | Mediana y rango, en Pa | Registrar diferencias ambientales; no esperar reproducir vacío lunar o presión marciana a cielo abierto. |
| P2 | Temperatura del suelo y agua del suelo | `stl1`, `stl2`, `swvl1`, `swvl2` | Métricas por capa, solo tras verificar profundidad y definición | Reanálisis terrestre; no prueba de hielo/permafrost ni de composición mineral. |
| P2 | Radiación solar incidente | `ssrd06`, si se verifica en el proveedor | Flujo medio tras conversión documentada de energía acumulada | No es radiación ionizante espacial ni mide directamente sombras locales. |

Las métricas anteriores son propuestas del equipo, no criterios oficiales NASA. Las unidades, acumulaciones, escalas y faltantes se verifican contra los metadatos del producto descargado. No sustituir `sp` por presión reducida al nivel del mar (`msl`) para describir la superficie de un sitio.

## Comparación de temperatura entre cuerpos

| Cuerpo | Producto a explorar | Qué se debe verificar |
|---|---|---|
| Tierra | MODIS Terra MOD11A1.061 | LST diurna/nocturna, emisividad, QA, hora de observación, nubes y cobertura. |
| Luna | Diviner: producto térmico derivado adecuado a la región | Magnitud exacta: temperatura de brillo por canal o temperatura física derivada; hora solar, geometría, estación y faltantes. |
| Marte | MGS TES: propiedad superficial derivada apropiada | Temperatura recuperada de superficie, emisividad, atmósfera/polvo, hora local, estación y cobertura. |

MOD11A1.061 ofrece LST diaria a 1 km con bandas de día/noche y controles de calidad/horario. No reconstruye por sí solo todos los máximos y mínimos diarios; las observaciones válidas bajo cielo despejado pueden sesgar la muestra. [Ficha NASA LAADS](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD11A1/).

Diviner incluye productos distintos y documenta faltantes en RDR. No mezclar temperatura de brillo de un canal con LST física sin justificar el tratamiento. [Archivo Diviner](https://pds-geosciences.wustl.edu/missions/lro/diviner.htm). TES archiva radiancias y propiedades atmosféricas y superficiales derivadas; falta seleccionar y abrir un producto térmico concreto. [Archivo TES](https://pds-geosciences.wustl.edu/missions/mgs/tes.html).

No comparar directamente `t2m` terrestre con temperatura de superficie lunar/marciana. Usar K para temperaturas absolutas y K para diferencias; convertir a °C solo para presentación cuando ayude. No confundir dos observaciones orbitales con una serie de ciclo completo.

El periodo diurno y el estacional de cada cuerpo tienen duraciones distintas. Comparar horas solares/fases y duración física de exposición según el objetivo, no emparejar fechas UTC. La misma temperatura no implica las mismas pérdidas térmicas: presión, atmósfera, viento y contacto con el terreno cambian el intercambio de calor. Mostrar tanto coincidencias de temperatura como límites del ensayo.

## Integración mínima propuesta

1. Mantener el scraper como gestor documental. Adquirir productos científicos por su descarga/API oficial.
2. Para la primera prueba terrestre de reanálisis, evaluar solo `skt` y `t2m`, unas pocas fechas/horas y un candidato. Medir bytes, tiempo, cobertura, unidades y escala real. Esto verifica acceso, no representa una climatología.
3. Si Earth2Studio funciona con un coste razonable, extraer las celdas regionales y guardar la selección y el origen del reanálisis. Si resulta costoso, conservar ERA5 como fuente y usar acceso directo mediante un cliente de datos con recorte adecuado.
4. Abrir una muestra terrestre MODIS y una muestra de un único cuerpo planetario; filtrar calidad y horarios. El componente térmico no depende de que todos los portales de scraping funcionen.
5. Exportar una tabla de mediciones y otra de métricas por sitio y periodo. Campos mínimos: sitio, cuerpo, variable física, producto/versión, tipo de evidencia, unidad, valor, tiempo UTC y solar cuando exista, periodo, soporte espacial, QA y fuente.
6. Mostrar ficha topográfica, ficha térmica y condiciones de campaña terrestre. Un campo ausente permanece desconocido; no se convierte en cumplimiento ni cero de similitud.

El primer entregable térmico será una comparación acotada de temperatura superficial y contraste entre horarios, con cobertura/limitaciones visibles. Una climatología, pronósticos y simulaciones son ampliaciones posteriores que requieren una necesidad de usuario concreta.

## Qué permanece pendiente

No se instaló Earth2Studio, no se descargaron datos ERA5/MODIS/Diviner/TES en esta revisión y no se ejecutó ningún modelo. La evaluación confirma capacidades declaradas en documentación/código; la viabilidad requiere completar la primera descarga y lectura. La presencia de indicadores climáticos no reemplaza evidencia de las cinco dimensiones originales: suelo, minerales, polvo, hielo y permafrost.
