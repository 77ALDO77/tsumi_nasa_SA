# Primeras pruebas del analizador: con qué datos comparamos

* **Autor:** 77aldo77
* **Fecha:** 2026-11-15
* **Estado:** brief de ideación. Lo revisaron 7 enfoques independientes. Nada de lo descrito está implementado todavía.
* **Contexto:** este brief continúa el diseño de la herramienta (v2, `/home/aldosantos/.opencode/plan/concepts_brief.md`). Parte de las 21 etiquetas de `scrapping/docs/etiquetas_analogos.json`.

## Resumen

Las primeras pruebas convierten cada análogo documentado por NASA en un **ejemplo de comparación**: un sitio terrestre frente a la región de la Luna o de Marte que NASA nombra. Solo se comparan las variables que miden la dimensión que NASA declaró, con una regla fijada antes de calcular y frente a una línea base. Los ejemplos que no se pueden medir se informan como «no medible» o como ruptura. El objetivo del autor es poder defender que, si el analizador llega a las mismas conclusiones que NASA en los análogos conocidos, también puede explorar otras zonas y encontrar análogos nuevos.

Conclusión de la revisión: **la idea se puede hacer, pero solo deja entre 1 y 2 ejemplos medibles en la Luna.** Con eso no se puede defender que el analizador generaliza. El argumento de los «análogos nuevos» tiene que apoyarse en otras pruebas (sección 2), y los ejemplos NASA pasan a ser casos ilustrativos, falsables y declarados por adelantado.

## Análisis

### 1. Qué queda medible al cruzar las etiquetas con los datos

Se cuenta por **pareja (sitio terrestre, región planetaria)**, no por etiqueta. Las 5 etiquetas de San Francisco Volcanic Field salen de un mismo artículo, así que no son independientes.

| Pareja | Qué declara NASA | ¿Se puede medir el relieve? | Datos verificados | Prioridad |
|---|---|---|---|---|
| Caja SFVF / Flagstaff (Cinder Lake, SP Crater) → polo sur | JETT3: «challenging terrain… near the lunar South Pole» | **Sí**, con pendiente y relieve | GLO-30 `N35_W112` y `N35_W111`; LOLA `ldem_80s_40m` | **P0, el único ejemplo de relieve** |
| SFVF → Marius Hills | Parecido geológico y de composición de las rocas | **En parte**: la morfología sí, la composición no. NASA no habla de relieve | SLDEM2015 (`00n_30n_270_315`, lectura por rangos 206, alturas en **km**) | P1, como «prueba de transferencia» |
| Valley of Ten Thousand Smokes → domos de Gruithuisen | «rock formations comparable…» (química) y «no tectonic plates» (ruptura) | **No**: la dimensión declarada es química | SLDEM2015 `30n_60n_315_360` | Al registro de límites |
| Kīlauea → Hadley Rille | Ensayo de tiempos de tareas. Hadley aparece solo como ilustración | **No** | — | No medible |
| Islandia → Luna | «landscape… scale of features» | **No**: falta el sublugar terrestre y la región lunar | — | No medible |
| Death Valley → Utopia Planitia | Terreno y evitación de peligros en Marte | Solo a la escala de MOLA (~463 m) | Sin DTM de HiRISE/CTX verificado | P2 |
| Askja, Medicine Lake, Atacama, Utah, Salda→Jezero, Verde Valley | Hielo, cuevas, química, biofirmas | **No** | — | Tabla de cobertura |
| Viento y foco en SFVF; ondulaciones de Islandia ×10; ausencia de tectónica | Rupturas o condiciones simuladas | — | — | Registro de límites |

Embudo honesto: **21 declaraciones NASA → unas 12 parejas → 1 medible en relieve en P0 (2 en P1)**. Las demás no son un fallo: muestran el alcance de la herramienta y responden a la pregunta de dónde se rompe la analogía.

### 2. Por qué el acuerdo con NASA no demuestra la generalización

Los siete revisores coinciden en esto.

- **NASA no evaluó relieve en casi ningún caso.** Eligió sitios por su geología, su logística, la composición de las rocas o tareas concretas. Si el relieve coincide, no se reproduce la conclusión de NASA. Si no coincide, tampoco la refuta.
- **El N es demasiado pequeño.** «Coherente en 1 de 1» o «en 2 de 2» es anecdótico, aunque esté bien hecho.
- **Lo que sí sostiene «el analizador puede encontrar análogos nuevos»** son estas cuatro pruebas, todas con la regla fijada antes de calcular:
  1. **Recuperación a ciegas.** Se busca en una caja amplia de la meseta de Arizona (2–3°, primero con GLO-90 y después con GLO-30) **sin usar las etiquetas**. Se informa en qué percentil quedan las ventanas de SFVF, Cinder Lake y SP Crater.
  2. **Tasa base global.** Se calcula qué fracción del terreno desnudo (filtrado con WorldCover) cae dentro de la envolvente lunar. Si es grande, por ejemplo más del 30 %, que haya coincidencia no dice nada y la prueba no discrimina.
  3. **Control negativo difícil.** Un terreno abrupto que no sea volcánico y que NASA no haya usado, como badlands o una montaña plegada. No sirve una llanura agrícola, porque cualquier método la descarta.
  4. **Un candidato nuevo** que iguale o supere a SFVF, con el desglose por variable, el intervalo de puestos y sus rupturas. Se presenta como «candidato de preselección para EVA/rover por relieve», nunca como «análogo NASA».

### 3. La referencia lunar: actualización y un posible choque

- **Situación del programa** (NASA, 23-10 y 04-11-2026). Artemis III es ahora una prueba en órbita terrestre en 2027. El primer aterrizaje, cerca del polo sur, es Artemis IV a principios de 2028. NASA describe una Moon Base en tres fases; la fase 1, hasta 2029, examina el polo sur. Las 9 regiones (Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1 y 2, de Gerlache Rim 2, Slater Plain) se citan como «nombradas en octubre de 2024 para el aterrizaje entonces asignado a Artemis III». No está verificado si NASA las mantiene para Artemis IV.
- **Qué mosaico cubre cada región.** Es una estimación a partir de centros publicados por terceros:
  - `ldem_875s`: solo de Gerlache Rim 2.
  - `ldem_85s`: Slater Plain, Haworth, Malapert Massif, Mons Mouton y Nobile Rim 1.
  - `ldem_80s`: Mons Mouton Plateau, Nobile Rim 2 y Peak near Cabeus B.

  Por defecto se usa `ldem_80s_40m_float.img` (924 MB, admite lectura por rangos).
- **Contornos de las regiones.** El data release de USGS (DOI `10.5066/P1MEQ6UK`, licencia CC0) está detrás de un reto de Cloudflare. Además, lo que publica son rejillas de navegación, no contornos, en archivos de 65 MB a 1,1 GB. Hace falta otra fuente citable: LROC QuickMap, el atlas del polo sur del LPI u otra. Hasta tenerla, la huella es «centro de terceros + radio declarado por el equipo».
- **Posible choque.** NASA eligió las regiones minimizando la variabilidad de la pendiente, pero JETT habla de «challenging terrain». Si la referencia es la elipse de aterrizaje, lo esperable es que Arizona sea más abrupta, es decir, una ruptura. **Hay que declarar antes de calcular** si la referencia es la zona de aterrizaje o su entorno de EVA (región más un margen de radio declarado), y en qué dirección se espera el resultado.

### 4. Línea base: dos preguntas distintas

- **Línea base cercana** (ventanas al azar en la misma caja): responde si el punto exacto destaca dentro de su zona. Alrededor de un campo volcánico todo es volcánico, así que no mide discriminación. Si el análogo no destaca, la lectura es «la analogía es regional», lo que apoya que dentro de la región puede haber otros sitios igual de válidos.
- **Línea base lejana o global** (otras cajas y terreno desnudo al azar): responde si la región destaca. Como NASA nombra regiones y no puntos, **esta es la que cuenta para el veredicto**.
- El muestreo se hace sobre `(grid_id, ix, iy)` con una semilla escrita en el preregistro, no sobre `window_id`.

### 5. Escala y fuentes de error

- Hay una **escalera de escalas fija**: 60, 120 y 240 m de píxel, con ventanas de 1,5 a 12 km. Se informa la forma de la curva de relieve frente a escala. **No se elige la mejor escala para cada ejemplo**, porque eso sería sobreajustar.
- **SLDEM2015** usa una proyección cilíndrica, así que el píxel no es cuadrado: a 36° N mide 59,2 × 47,9 m. Sus alturas están en km. Se reproyecta cada recorte a una proyección local sobre una esfera de 1737,4 km y se pasa a metros al leer. Una prueba sin red comprueba el rango de las alturas.
- **LOLA** tiene píxeles sin disparos láser que están interpolados y suavizan la pendiente: se enmascaran con `ldec`. **GLO-30** es un modelo de superficie con artefactos de radar en laderas. Si el resultado cambia de signo entre escalas, se informa como inestable.
- **Prueba sintética:** un plano inclinado a 10° debe devolver 10° ± 0,1° con la misma función para los dos cuerpos.
- **Escala de los rasgos.** Los conos de SFVF miden cientos de metros; los domos de Marius y Gruithuisen, kilómetros. Es una hipótesis que hay que confirmar con la literatura. Si se confirma, se registra como `se_rompe: escala` con el factor medido. No se fuerza la coincidencia.

### 6. Corrección de las etiquetas (errores del primer pase)

- **Error en la herramienta.** `prepare_analog_labels.py:56` escribe siempre `revision_humana: "pendiente"` y borra cualquier revisión hecha. Debe leer `revision_humana`, `revisor` y `fecha_revision` del archivo de entrada. También hay que corregir dos cosas: el `KeyError` que no indica el `label_id`, y `autoridad_fuente` fijo en «nasa», que debe venir de la entrada. Falta además una prueba para la herramienta.
- **Literales recortados.** Hay que ampliarlos hasta que nombren la región o el cuerpo dentro de la propia cita: JETT3 («…near the lunar South Pole»), VTTS («…comparable to the Moon's Gruithuisen Domes»), Medicine Lake, ondulaciones de Islandia, Verde Valley, Utah y VTTS-Marte.
- **Divisiones y reclasificaciones:**
  - VTTS se divide en dos etiquetas: similitud de composición y ruptura por tectónica.
  - `SFVF-ROCAS-01` pasa a «no medible por escala».
  - `SFVF-SIM-01` tiene como región «Luna» en general.
  - Islandia y D-RATS pasan a «no medible: sin coordenadas». D-RATS es un rover presurizado, no EVA.
  - Utah se marca como ilustración, igual que Hadley.
- **Vocabulario cerrado.** `dimension` usa hoy 19 textos libres. Se sustituye por un vocabulario cerrado y una tabla versionada `dimension_measures`. Si una dimensión no tiene filas en esa tabla, el ejemplo es «no medible». Así lo decide el dato y no una persona caso a caso.
- **Expectativa en el preregistro.** La expectativa se mueve de la etiqueta al preregistro de cada ejemplo. La etiqueta queda solo como evidencia.

### 7. Coordenadas terrestres con fuente citable (verificadas)

| Sitio | Coordenadas | Fuente |
|---|---|---|
| San Francisco Volcanic Field | 35,347, −111,678 | Smithsonian GVP 329020 (WFS) |
| SP Crater | 35,5822, −111,6318 | USGS GNIS 33907 |
| Cinder Lake (clase Flat) | 35,3197, −111,5171 | USGS GNIS 27656 |
| Kīlauea | 19,421, −155,287 | Smithsonian GVP 332010 |
| Novarupta | 58,2655, −155,1588 | Smithsonian GVP 312180 |
| Valley of Ten Thousand Smokes | 58,3967, −155,3905 | USGS GNIS 1411625 |
| Death Valley (clase Basin) | 36,2466, −116,8170 | USGS GNIS 270787 |

**Black Point Lava Flow no existe en GNIS.** Solo hay un «Black Point» de clase Bench, sin confirmar. Se usa la caja SFVF completa, que lo contiene.

### 8. Cambios al modelo de datos v2

- `analog_labels`:
  - la clave primaria pasa a ser `label_id` (texto);
  - se añaden `region_site_id` (clave foránea, puede ser nula) y `region_text`;
  - se quita `UNIQUE(site_id, analog_body, dimension, relation)`, que rechaza SFVF-SIM y SFVF-MARIUS;
  - se quita `team_expectation`.
- `sites`: se añaden `footprint_crs`, `footprint_asset_id`, `center_lat`, `center_lon`, `lon_convention` y `bbox_deg`. Así hay huellas planetarias sin necesidad de un SRID lunar, incluidas las de latitudes medias.
- Tablas nuevas:
  - `dimension_measures(dimension, map_version, pair_id, statistic, justification, frozen_at)`
  - `validation_examples(example_id, label_id, earth_site_id, region_site_id, map_version, search_id, expectation, coincidence_rule jsonb, seed, n_baseline, exclude_site, prereg jsonb, prereg_hash UNIQUE, frozen_at, git_commit)`
  - `baseline_members(example_id, grid_id, ix, iy)`
  - `example_verdicts(example_id, run_id, prereg_hash, code_version, verdict, reason, site_percentile, n_baseline_valid, metricas_preexistentes, detail)`
  - `example_sets` y `example_set_members`, que congelan N
- Vista `v_coherence(set_id, k, n_medibles, n_no_medible, n_sitios, n_fuentes)`.
- **Cada ejemplo reutiliza `searches`:** su región es la referencia de una `profile_version` y su caja es un `search_space` de tipo `box`. Los ejemplos con la misma región, caja y variables comparten búsqueda gracias a `spec_hash`. Las etapas de coherencia van a `validation_results`.
- **Qué se puede afirmar sobre el preregistro.** Lo honesto es «registrado antes de la ejecución del veredicto», no «antes de que existieran métricas», porque hay caché compartida. El JSON del preregistro se confirma en git. La base guarda `prereg_hash` y el commit. Una prueba comprueba que `frozen_at < runs.started_at`, y se publica `metricas_preexistentes`.
- **N** solo cuenta `similitud_documentada` y `uso_documentado` con alguna variable medible. Las rupturas van a `limits_register`.

### 9. Cómo se presenta

- **Ficha por pareja**, con estos campos:
  - la cita de NASA y su fuente;
  - el sitio, separando lo que dice NASA de lo que eligió el equipo;
  - la región y su huella;
  - la dimensión declarada y si es medible;
  - la regla, con su hash y fecha;
  - los valores en unidades frente a la envolvente;
  - la línea base, dicha en palabras: «más cerca que 184 de 200 ventanas al azar»;
  - el veredicto y los límites.
- **Veredictos permitidos:** `coherente con la declaración de NASA`, `no coherente con la declaración de NASA`, `no medible (motivo)` y `ruptura documentada por NASA`. No se usan «validado», «confirmado», «análogo NASA», «precisión» ni porcentajes.
- **Pie fijo:** «NASA no evaluó esta herramienta. Comparamos nuestras métricas con lo que NASA publicó sobre el sitio».
- **El embudo completo** y, cuando N ≤ 5, en el mismo tamaño de letra: «N demasiado pequeño para estimar una tasa; casos ilustrativos». Junto al embudo va siempre el resultado del control negativo.
- **Los no medibles** van en una tabla de alcance agrupada por motivo, sin color rojo. Las rupturas van en la columna «Dónde NASA dice que no se parece».
- **Glosario:**
  - *ejemplo de comparación*: pareja (sitio, región) con sus citas;
  - *dimensión declarada*: aquello en lo que, según la frase de NASA, se parecen;
  - *variable medible*: variable con papel de similitud que mide esa dimensión;
  - *regla prerregistrada*: criterio con hash, fijado antes del veredicto;
  - *línea base*: ventanas al azar, cercanas y lejanas.

### 10. Resultado ideal y contradicciones

| Contradicción | Resolución |
|---|---|
| N diminuto frente a la afirmación de generalización | Cada ejemplo es una predicción falsable, no una muestra. La generalización se defiende con la recuperación a ciegas, la tasa base y el control negativo |
| Declaración cualitativa frente a salida numérica | Predicción de orden escrita antes de calcular: «la región R queda más cerca de S que el percentil P de la base». Se compara un orden, nunca una cifra con NASA |
| Una referencia distinta por ejemplo frente a una sola referencia Artemis | La referencia ya es un parámetro. En P1, matriz cruzada K×K: cada sitio debe quedar más cerca de su región NASA que de las otras. Con K=3, la p mínima es 0,17, y se dice |
| Rasgos de tamaños distintos frente a una escala común | Escalera fija de escalas; la escala con mejor coincidencia se informa como dato y no decide el veredicto |
| Línea base con la misma geología | Dos líneas base con preguntas declaradas; el veredicto usa la lejana o global |
| Etiquetas no medibles frente a usar todas | Las 21 aparecen en la tabla de cobertura; solo las medibles cuentan en k/N |

## Objetivos y no objetivos

* **Objetivos (P0):**
  * Corregir la herramienta y las etiquetas (sección 6) y hacer la revisión humana de los literales.
  * Preregistro en git:
    * el mapa entre dimensión y variables;
    * las parejas y su expectativa;
    * la referencia polar, indicando si es zona de aterrizaje o entorno de EVA con radio declarado;
    * la escalera de escalas y las métricas;
    * las semillas y los umbrales.
  * Un ejemplo de relieve: la caja SFVF/Flagstaff frente a una región polar.
  * Recuperación a ciegas en una caja amplia de Arizona.
  * Tasa base de terreno desnudo.
  * Un control negativo difícil.
  * Tabla de cobertura de las 21 etiquetas y registro de límites con las rupturas.
  * Ficha y embudo según la sección 9.
* **Objetivos (P1):**
  * Prueba de transferencia SFVF → Marius Hills con SLDEM2015.
  * Segunda región polar como autoconsistencia.
  * Escala de 120 m.
  * Matriz K×K si hay al menos 3 regiones con datos.
* **Objetivos (P2):**
  * Death Valley → Utopia, con MOLA o un DTM.
  * Morfología de Gruithuisen.
  * Detección de conos y domos.
* **No objetivos:**
  * Presentar «k de N» como validación o como tasa.
  * Afirmar que NASA valida la herramienta.
  * Ajustar escala, variables o regla después de ver los datos.
  * Contar etiquetas en vez de parejas.
  * Usar Gruithuisen como ejemplo positivo.
  * Medir rocas o química con un DEM.
  * Ajustar la mejor escala para cada ejemplo.

## Alternativas descartadas

* **«Reproducir el resultado de NASA» como prueba de que el analizador funciona.** Se descarta porque NASA no publicó un ranking ni evaluó el relieve en la mayoría de los casos. Se sustituye por casos falsables declarados de antemano, más recuperación a ciegas y tasa base.
* **Usar como ejemplos medibles todas las etiquetas con expectativa «positivo».** Se descarta: rocas a escala de centímetros, sitios sin coordenadas y regiones que solo ilustran no se pueden medir.
* **Línea base solo con ventanas cercanas.** Se descarta porque comparte la geología del análogo y no mide discriminación.
* **Llanura agrícola como control negativo.** Se descarta porque cualquier método la descarta; no pone a prueba nada.
* **Elegir la mejor escala para cada ejemplo.** Se descarta por sobreajuste con N ≤ 3.
* **El data release de USGS como fuente de los contornos de las regiones.** Se descarta por ahora: está bloqueado por Cloudflare y publica rejillas de navegación, no contornos.
* **LOLA `ldem_512_*` para latitudes medias.** Se descarta: pesa 4,2 GB por tesela y no aporta nada frente a SLDEM2015.
* **Detectar conos para medir su altura y diámetro.** Es la comparación más defendible geológicamente, pero cuesta más de 8 h y no hay forma de validarla. Queda en P2.
* **Usar como pareja Kīlauea → Hadley.** Se descarta: en el texto de NASA, Hadley es solo una ilustración.

## Decisiones clave y siguientes pasos

**Decidido:**

1. Las primeras pruebas son ejemplos falsables por pareja, no una validación estadística.
2. El argumento de los «análogos nuevos» se apoya en la recuperación a ciegas, la tasa base, el control negativo y un candidato nuevo.
3. El veredicto usa la línea base lejana o global, y la escalera de escalas es fija.
4. Las fuentes verificadas son:
   - LOLA `ldem_80s_40m`, que se usa por defecto;
   - SLDEM2015 para latitudes medias;
   - GLO-30 y GLO-90 en AWS;
   - coordenadas de GVP y GNIS.
5. La expectativa y la regla se registran en git antes del veredicto.

**Pendiente:**

1. **Región polar de referencia** y si se usa la zona de aterrizaje o el entorno de EVA (con qué radio), junto con la dirección esperada para la caja de Arizona.
2. **Fuente citable para la huella de las regiones**, como LROC QuickMap o el atlas del LPI. Hasta entonces, centro de terceros y radio declarado.
3. **Control negativo difícil:** qué sitio y con qué fuente.
4. **Quién revisa los literales** y cuándo. La corrección de la sección 6 va antes.
5. **Comprobar en la literatura** los diámetros de los conos de SFVF y de los domos lunares, que son una hipótesis de escala.
6. **Capa del WMS de USGS para la Luna no polar**, necesaria para el panel de Marius Hills (P1). No está verificada.
