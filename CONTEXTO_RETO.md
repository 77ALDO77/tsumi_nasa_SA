# Contexto actualizado del reto

Actualizado el 14 de noviembre de 2026 a partir de la transcripción del autor, la rúbrica facilitada por el equipo y los antecedentes documentados en el proyecto.

## Encargo y público

**Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars** invita a buscar en la Tierra lugares, ambientes o procesos útiles para preparar operaciones lunares o la exploración de Marte. El autor permite investigar un solo lugar, comparar varios o diseñar un método de búsqueda. El equipo debe explicar en qué funciona la analogía, cómo de bien funciona y dónde falla. La gravedad, el vacío lunar, la atmósfera marciana y la radiación delimitan lo que puede extrapolarse.

El público primario propuesto son investigadores y equipos que preparan ensayos. Para ellos importa una decisión concreta, por ejemplo elegir un lugar donde probar una técnica de caracterización de materiales. Los equipos universitarios y educadores son usuarios secundarios propuestos. La necesidad específica del usuario sigue pendiente de validación.

## Variables propuestas por el equipo

| Dimensión | Pregunta que deberá resolver la evidencia |
|---|---|
| Suelo o material superficial | ¿Qué propiedad se compara, como tamaño de grano, textura o comportamiento mecánico? Documentar método y profundidad de muestreo. |
| Minerales | ¿Qué fase o conjunto de minerales identifica el instrumento? Registrar técnica, resolución y ambigüedades. |
| Polvo | ¿Se estudia composición, transporte, deposición o adherencia? Un resultado para un proceso tiene alcance limitado sobre los demás. |
| Hielo | ¿Qué evidencia identifica hielo, a qué profundidad y con qué cobertura? Las condiciones térmicas favorables solo sustentan una hipótesis de presencia. |
| Permafrost | ¿Hay observaciones térmicas del terreno durante el periodo y a la profundidad necesarios para caracterizar congelación persistente? Documentar por separado la evidencia del contenido de hielo. |

La transcripción contempla también relieve, temperatura, iluminación, volcanismo, cuevas, navegación y operaciones humanas o robóticas. Se pueden elegir cuando respondan a la pregunta seleccionada. La topografía para recorridos es una alternativa pendiente de la comparación documental y de muestras reales.

## Siete antecedentes geográficos del video

El punto de partida es **desierto de Atacama, Antártida, Islandia, Hawái, desierto de Mojave, Valle de la Muerte y cráter de impacto Haughton**. Para cada nombre se buscará un sublugar o estudio concreto. La mención en el video acredita que el autor lo ofrece como antecedente. Las asociaciones con suelo, minerales, polvo, hielo o permafrost requieren evidencia específica. Los sitios conocidos servirán para entender métodos o construir controles. El aporte propio podrá ser un lugar inesperado, una relación respaldada por datos o una mejora del método.

## Evidencia ya disponible

- El inventario reúne 11 enlaces, incluidos Earthdata, Worldview, PDS, LRO/Diviner y recursos de CSA, ESA y JAXA. Sirven para localizar productos. La viabilidad del MVP depende de abrir las muestras elegidas. [Inventario del equipo](resources.txt)
- JETT aporta un antecedente sobre el uso de terreno terrestre y condiciones de ensayo simuladas. La documentación investigada sustenta una selección según objetivo. En las fuentes revisadas sigue sin identificarse una fórmula universal de elegibilidad NASA. [Caso NASA JETT3](https://www.nasa.gov/humans-in-space/nasa-to-practice-artemis-moonwalking-roving-operations-in-arizona-desert/) · [Protocolo de criterios](docs/INVESTIGACION_CRITERIOS.md)
- Ya existen comparadores visuales, repositorios de sitios y bibliotecas de materiales. PTAL describe caracterización espectral de muestras terrestres en contextos geológicos de Marte. El uso de una referencia documental debe distinguirse de una medición propia. [NASA Analog Explorer](https://science.nasa.gov/solar-system/analog-explorer/) · [PTAL](https://doi.org/10.1002/jrs.5652) · [Estado del arte](docs/ESTADO_DEL_ARTE.md)

## Condiciones del proyecto

La ventana de planificación es de 34 horas. Quedan por confirmar el reparto del equipo y los requisitos de envío de su sede. La rúbrica aportada usa impacto, creatividad, validez, relevancia y presentación en escala de 1 a 5. Los pesos internos de selección de ideas pertenecen a AGENTS.md.

El proyecto cuenta con planificación, una revisión documental inicial y un extractor documental con Scrapling, organizado en `scrapping/`. La revisión de 17 URLs recuperó texto de 11 fuentes y registró las limitaciones de acceso o contenido de las otras 6. Se corrigió el acceso TLS a CSA con una cadena validada y se revisaron los selectores y el muestreo documental. Los 27 pasajes candidatos siguen pendientes de revisión humana; no equivalen a mediciones comparables. La selección de métricas, la prueba de datos científicos y la validación de candidatos corresponden a las próximas etapas. [Implementación y ejecución](scrapping/README.md) · [Análisis de errores y resultados](scrapping/docs/ANALISIS_RESULTADOS.md) · [Plan de ejecución](PLAN_HACKATHON.md) · [Flujo de trabajo](FLUJO_TRABAJO.md)
