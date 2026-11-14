# Estado del arte: selección y caracterización de análogos planetarios

Fecha de consulta inicial: 14 de noviembre de 2026.
Estado: revisión exploratoria inicial; no es una revisión sistemática exhaustiva. Se han consultado páginas institucionales, resúmenes y metadatos; no se han ejecutado las herramientas ni reproducido todos los métodos. La lectura integral de publicaciones técnicas sigue pendiente cuando se indica.

## Preguntas de revisión

1. ¿Cómo se justifica que un sitio sea análogo para una pregunta científica o ensayo concreto?
2. ¿Qué variables se miden, a qué escalas y con qué incertidumbres?
3. ¿Qué catálogos, herramientas de comparación y repositorios ya existen?
4. ¿Qué evidencia permite evaluar resultados y qué limita su transferencia a Luna o Marte?
5. ¿Qué mejora concreta podemos implementar y demostrar en la hackathon?

## Comparación inicial de antecedentes

| Referencia | Aporte documentado | Alcance o límite de nuestra lectura | Consecuencia para el proyecto |
|---|---|---|---|
| NASA Planetary Analog Explorer | Galería interactiva de pares Tierra–otros mundos, con contexto científico | Se revisó la página; no es evidencia de un motor global de búsqueda cuantitativa | Una comparación visual por sí sola ya tiene antecedentes; debemos aportar evidencia y método |
| USGS Terrestrial Analogs Data Portal (TADP) | La descripción indexada lo identifica como repositorio y herramienta de descubrimiento para datos terrestres relevantes a ciencia planetaria, apoyado en ScienceBase | La página dinámica no fue legible en esta consulta; verificar funciones, registros y acceso programático | Investigar reutilización del catálogo antes de crear otro; no afirmar inexistencia de repositorios |
| Edgar et al., USGS 2024, OFR 2024–1042 | Encuesta sobre uso de sitios, portales, datos y muestras; identifica necesidades de acceso, archivo, formación y comunicación | Se consultó el resumen ejecutivo y metadatos; no se leyó todo el informe | Sustentar necesidades en evidencia comunitaria y comprobar qué ha cambiado desde 2024 |
| Europlanet 2024 RI, TA1 | Red de sitios caracterizados para condiciones y objetivos científicos distintos | Página archivada: el proyecto cerró en julio de 2024; no asumir vigencia de sus ofertas ni restricciones | Extraer categorías y caracterización; revisar disponibilidad actual por separado |
| Huff et al., JETT5, 2023 | Selección contextual y cartografía multifuente para operaciones lunares simuladas | Resumen de congreso; no equivale a protocolo universal ni estudio reproducido | Vincular escala, datos y objetivo; registrar acceso y diversidad geológica separadamente |
| NASA JETT3, informe de 2023 | Configuración de ensayos y condiciones simuladas, incluida iluminación | Consulta parcial; lectura de secciones pertinentes pendiente | Separar condiciones naturales de condiciones creadas mediante equipos |
| Stern et al., 2025, JGR Planets | Marco de evaluación de sitios para mundos oceánicos relacionado con objetivos, mediciones, logística y límites | Lectura parcial; alcance planetario diferente al MVP | Adaptar estructura de razonamiento, sin copiar umbrales específicos de hielo/habitabilidad |
| Veneranda et al., 2020, PTAL Raman | Caracterización espectral de materiales análogos ligados a contextos geológicos marcianos | Resumen y metadatos del artículo; copia en arXiv depositada en 2021 | Si elegimos mineralogía, exigir evidencia espectral pertinente; no inferir composición por color |

## Referencias iniciales

- NASA, Planetary Analog Explorer: https://science.nasa.gov/solar-system/analog-explorer/
- USGS, Terrestrial Analogs Data Portal: https://tadp.astrogeology.usgs.gov/
- Edgar, L. A., et al. (2024). Assessing community needs for terrestrial analog studies. USGS Open-File Report 2024–1042. https://doi.org/10.3133/ofr20241042
- Europlanet 2024 RI, TA1 Planetary Field Analogues (archivo): https://www.europlanet.org/europlanet-2024-ri/ta1-pfa/
- Huff, A. E., et al. (2023). JETT5 Geologic Mapping in Support of Simulated Artemis Surface Operations: Process and Preliminary Products. Resumen de congreso. https://ntrs.nasa.gov/citations/20230010127
- NASA (2023). EHP Joint EVA & HSM Test Team (JETT) Field Test 3 (JETT3), EHP-20021. https://ntrs.nasa.gov/api/citations/20230010686/downloads/EHP-20021_JETT3_Test_Report_Baseline_20230010686.pdf
- Stern, J. C., et al. (2025). A comprehensive framework for assessing terrestrial analogue field sites for ocean worlds. JGR: Planets, 130, e2024JE008803. https://doi.org/10.1029/2024JE008803
- Veneranda, M., et al. (2020). PTAL multi-spectral database of planetary terrestrial analogues: Raman data overview. Journal of Raman Spectroscopy, 51(9), 1731–1749. https://doi.org/10.1002/jrs.5652 ; copia de autores: https://arxiv.org/abs/2101.08305

## Criterios de inclusión y evaluación

Priorizar estudios originales y documentación institucional relacionados con selección, medición, validación o uso de análogos. Incorporar revisiones para organizar antecedentes y seguir sus referencias primarias. Excluir comparaciones solo estéticas y afirmaciones sin procedencia para definir métricas.

Autoridad institucional, revisión por pares y reproducibilidad son dimensiones distintas. Un dominio oficial no garantiza que una afirmación se aplique a nuestro objetivo. Una publicación antigua puede aportar método, pero sus afirmaciones sobre disponibilidad o ausencia de herramientas requieren comprobación actual.

Registrar por referencia: año, tipo, objetivo, sitio, cuerpo de referencia, método, variables, datos, escala, validación, incertidumbres, limitaciones, disponibilidad de código/datos y decisión que informa. Desconocido no significa inexistente.

Los repositorios de otros participantes serán antecedentes de producto separados, con autoría reconocida. No se tomarán como validación científica ni se reutilizará código sin comprobar licencia y atribución.

## Hipótesis de contribución, aún no demostrada

Integrar evidencia documental revisada y mediciones comparables en un expediente por candidato: objetivo de uso, coincidencias, diferencias, calidad de evidencia y validaciones pendientes.

No afirmar que nadie realiza esta integración. Debe compararse con herramientas existentes y demostrarse una mejora concreta para una tarea acotada. No son aportes suficientes por sí solos: mapa, scraping, chatbot o ranking.

## Traducción del estado del arte a software

Referencia → criterio respaldado → requisito del usuario → dato y métrica → componente → comprobación → resultado demostrable.

Ejemplos propuestos:
- Escala de cartografía en JETT → documentar escala pertinente → metadatos visibles y procesamiento compatible → comprobar que no se atribuye detalle inexistente.
- Condiciones simuladas en JETT3 → distinguir naturaleza/equipos → expediente con límites → revisar que no se atribuya iluminación lunar natural al sitio.
- Necesidades de archivo USGS → registrar procedencia → resultados exportables con identificadores → comprobar que cada resultado llega a su fuente.
- Evaluación contextual de Stern et al. → empezar por objetivo → criterios dependientes del caso de uso → comprobar que no se etiqueta un candidato como universalmente apto.

## Cierre de la revisión inicial

Al finalizar la ventana inicial entregar: matriz comparativa revisada, bibliografía, una brecha formulada como hipótesis, selección del caso de uso, métricas candidatas y prueba de disponibilidad de datos. La revisión deberá conducir a una decisión implementable y no retrasar indefinidamente MVP 0.
