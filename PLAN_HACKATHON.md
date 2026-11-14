# Plan definitivo de la hackathon · 34 horas

**Entrega prevista.** Un investigador o un equipo universitario de exploración podrá elegir un objetivo de estudio, examinar al menos un candidato terrestre y explicar con observaciones NASA qué rasgo comparte con una región concreta de la Luna o Marte, cuánto se parecen a la escala examinada y dónde se rompe la analogía.

El calendario, los entregables y las decisiones de recorte quedan definidos aquí. La elección científica se hará en dos momentos. En H3 se elegirá la hipótesis mejor sustentada por las fuentes. En H7 se fijará el alcance que los datos permitan demostrar. Las horas se cuentan desde el inicio del equipo. Conviene anotar la hora límite del evento local y ajustar el calendario a ella.

[Contexto científico y antecedentes](CONTEXTO_RETO.md) · [Flujo de trabajo](FLUJO_TRABAJO.md)

## Alcance y decisiones

| Prioridad | Resultado previsto |
|---|---|
| P0 | Matriz de antecedentes de los siete sitios y las cinco dimensiones candidatas. Cada asociación utilizada en el método tendrá una referencia localizable. Las lagunas quedarán explícitas. |
| P0 | Una pregunta científica o de ensayo, una referencia planetaria delimitada, un candidato terrestre delimitado y una comparación de control. Al menos un producto NASA debe intervenir en el resultado. |
| P0 | Una comparación reproducible con datos reales, unidades, escala y límites. Se buscarán dos métricas complementarias cuando las fuentes las justifiquen. Una medición bien sustentada permite cerrar un caso más estrecho. |
| P0 | Mapa o figura comparativa y expediente con fuentes, evidencia, interpretación, aplicación posible y limitaciones. Demo, instrucciones y entrega accesibles. |
| P1 | Más candidatos, comprobación adicional de sensibilidad y revisión por un usuario o especialista si está disponible. |
| P2 | Segundo cuerpo planetario, búsqueda geográfica más amplia o dimensiones científicas adicionales. |

En H3 compararemos hasta tres enfoques que surjan del estado del arte. Usaremos la matriz interna del proyecto para estimar alineación (25 %), factibilidad (20 %), impacto (15 %), diferenciación (15 %), solidez (15 %) y demo (10 %). Para cada nota anotaremos su evidencia y el supuesto más débil. Una propuesta cuya propiedad indispensable sea imposible de observar con los datos disponibles exigirá reformular la pregunta. La rúbrica del jurado se aplicará por separado al producto.

## Calendario y criterios de aceptación

| Horas | Entrega | Evidencia necesaria para avanzar |
|---|---|---|
| 0–3 | Investigación y elección provisional | Matriz de sitios, dimensiones, fuentes y vacíos. Una pregunta priorizada, una alternativa de respaldo, productos candidatos y requisitos del evento registrados. |
| 3–7 | MVP 0 · Viabilidad | Abrir una muestra de cada cuerpo. Registrar procedencia, unidades, cobertura, escala y una medición comparable. Decidir continuar, cambiar de producto o reducir el caso. |
| 7–14 | MVP 1 · Análisis | Reproducir el resultado desde las muestras. Comparar el candidato con un caso contrastante y explicar qué característica cambia. |
| 14–21 | MVP 2 · Integración | Recorrer de principio a fin la pregunta, la referencia, el lugar terrestre, la evidencia y los límites. Verificar que cifras y fuentes coincidan con las salidas del análisis. |
| 21–26 | MVP 3 · Demo | Revisar al menos un supuesto que afecte a la conclusión, por ejemplo la ventana espacial, la incertidumbre o la selección de muestras. Congelar funciones en H26. |
| 26–30 | Validación y documentación | Otro integrante, o una segunda ejecución limpia, puede reproducir la comparación. Revisar afirmaciones, atribuciones y acceso público. |
| 30–34 | MVP 4 · Entrega | Ensayar el pitch, abrir los enlaces desde una sesión sin autenticar y preparar copia local. Objetivo interno de envío en H32 con dos horas de margen si el cierre local lo permite. |

## Construcción y reparto

Un responsable de ciencia y datos mantiene la matriz, las muestras y el cálculo. Un responsable de producto integra los resultados en la demo. Un responsable de entrega reúne fuentes, prueba reproducibilidad y adapta el pitch al formato confirmado. Una persona puede asumir varias responsabilidades. Con dos personas, compartir el esquema del expediente al inicio permite preparar la interfaz mientras se comprueban las mediciones.

La arquitectura prevista consiste en extracción documental acotada, revisión humana, procesamiento local en Python y exportación de resultados con identificadores de fuentes. Una vista estática puede leer esos resultados sin exigir conexión al catálogo durante la demo. React/TypeScript encaja si facilita explorar candidatos. Un estudio de sitio único puede entregarse con un mapa y una ficha reproducible. Los servicios en línea se elegirán según la disponibilidad real del equipo.

## Decisiones de contingencia

- Si la extracción automática falla, registrar manualmente los pasajes imprescindibles con URL y página. La decisión científica puede continuar.
- Si en H7 falta una medición comparable, probar el producto de respaldo o una pareja documentada más estrecha. Declarar qué hipótesis quedó sin evaluar.
- Si el orden de los candidatos se invierte con un cambio razonable de escala o pesos, mostrar las diferencias por característica y explicar la sensibilidad.
- Si en H14 el cálculo sigue incompleto, concentrar el resto de la construcción en un candidato y un control.
- Si falla el mapa en línea, usar la figura exportada y los resultados locales para demostrar el mismo caso.

## Evaluación y entrega

En H7, H21 y H30 revisar las cinco dimensiones en escala de 1 a 5 según la rúbrica facilitada por el equipo. Sustentar impacto con una decisión concreta de usuario, creatividad con una mejora frente a un antecedente, validez con una comparación reproducida, relevancia con la intervención identificable de NASA y presentación con una demo comprensible. Registrar los bloqueantes y asignar cada corrección a una persona.

El guion seguirá una sola pregunta hasta su respuesta. Mostraremos el candidato y el control, explicaremos una medición, señalaremos una diferencia que limita su uso y cerraremos con el ensayo o estudio que la evidencia permite proponer.
