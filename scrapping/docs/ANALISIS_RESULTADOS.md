# Errores y utilidad de las fuentes extraídas

Revisión del 14 de noviembre de 2026. Punto de partida: tu ejecución `20261114T163415819391Z`. Se repitieron las ocho fuentes problemáticas después del cambio de red reportado y se revisó el contenido de las fuentes recuperadas.

**Resultado actual: 11 fuentes con texto extraído, 6 con limitaciones, 27 pasajes candidatos y 293 enlaces.** Hay 17 URLs en total. Las dos recuperaciones adicionales son RCM y RADARSAT-1. No se ha descargado ni comparado un producto científico terrestre con uno planetario.

[Resumen actual](../data/resultado-revisado/resumen.md) · [Manifest y hashes](../data/resultado-revisado/manifest.json) · [Auditoría JSON](analisis_fuentes.json) · [Tabla CSV](analisis_fuentes.csv)

## Qué fallaba y qué cambió

| Fuente | Diagnóstico comprobado | Resultado y acción |
|---|---|---|
| Earthdata Search | HTTP 200 con interfaz que pide JavaScript. El fetcher HTTP no ejecuta la aplicación. | Sigue `requiere_javascript_o_api`. Para obtener productos hay que consultar su catálogo oficial o implementar una integración de su API; repetir el HTML no añade mediciones. |
| Worldview | `/robots.txt` responde HTTP 200, `text/html`, con título «Page not found - NASA Worldview». | Sigue `robots_no_disponible`: es una página de error presentada con 200. El programa omite la portada por su política conservadora; esto no demuestra que NASA prohíba toda extracción. |
| ESA Open Science Catalogue | `/robots.txt` devuelve la propia aplicación HTML, con referencias a un navegador STAC. | Sigue `robots_no_disponible`. Se necesita una ruta oficial de catálogo y revisar sus condiciones; no se ha implementado esa integración. |
| RCM y RADARSAT-1 | Scrapling/curl_cffi devuelve código 60, emisor de certificado no resoluble. El cliente de Windows con Schannel sí valida y obtiene HTTP 200 en robots. | **Resuelto para ambas fuentes:** un PEM que incluye la cadena de CSA validada por Windows permite extraer las fichas con TLS activo. |
| JAXA G-Portal | El selector genérico recuperaba solo «Related links», aunque el HTML tenía navegación por sensores, magnitudes y CSW/SFTP. | Selector corregido: 16 segmentos y 17 enlaces. Nuevo estado `portal_navegacion`; se conserva su utilidad como índice sin contarlo como evidencia científica. |
| Yungay y PTAL | DOI redirige correctamente; el editor devuelve HTTP 403. Persistió en el reintento. | Sigue `bloqueo_acceso`. El código no permite atribuir la causa exclusivamente a la red, un pago o una IP. Usar una copia de autor/repositorio autorizada si está disponible; no se ha descargado una alternativa. |

Cambiar de red no resolvió estos ocho casos en el reintento. En CSA, la comparación entre clientes aisló una diferencia de validación de certificados; no demuestra que el router fuera la causa. Exportar ROOT/CA de Windows por sí solo no bastó: fue necesario agregar la cadena que Windows construyó y validó para CSA. No se desactivó TLS ni se instalaron autoridades nuevas en el sistema. [Cómo curl valida certificados](https://curl.se/docs/sslcerts.html) · [Códigos de error de libcurl](https://curl.se/libcurl/c/libcurl-errors.html).

La evidencia de red está en [revision-nueva-red](../data/revision-nueva-red/manifest.json), sus [respuestas de robots](../data/revision-nueva-red/robots.json) y [csa-cadena-verificada](../data/csa-cadena-verificada/manifest.json). Los certificados públicos y su procedencia local se guardan en `scrapping/certs/`, excluida de Git.

## Problemas del extractor encontrados durante la revisión

1. **Errores TLS clasificados como red genérica.** Ahora distingue `error_tls`, `timeout` y `error_red`; conserva código de curl, URL y fase. Un fallo de certificado no se reintenta como si fuera una desconexión temporal.
2. **Muestreo sesgado en Mojave.** Los 20 pasajes originales procedían de las páginas PDF 1–14, aunque el informe tiene 123 páginas. Ahora se recorren los 120 pasajes candidatos antes de seleccionar 20 distribuidos a lo largo del documento; se reserva una mención de cada sitio encontrado cuando cabe. La muestra alcanza la página 123, pero no constituye lectura exhaustiva.
3. **Navegación mezclada con evidencia.** Cambridge incluía un breadcrumb y el título como candidatos; ahora se limita al panel del artículo y los encabezados no generan evidencia por sí solos. GitHub se limita al README del repositorio.
4. **Un fallo de selector parecía falta de contenido en JAXA.** Se recuperó la navegación y se etiquetó por su función real.
5. **La cuenta de pasajes podía interpretarse como calidad científica.** Se añadió una auditoría reproducible con segmentos, longitud, enlaces, límites de muestreo y páginas sin texto. No genera puntuaciones de similitud ni de validez.

La reducción de 32 a 27 pasajes tras añadir dos fuentes tiene explicación: se eliminaron coincidencias en títulos y navegación. No significa que se hayan perdido mediciones. Los documentos y cuerpos originales se conservan.

## Qué aportan las once fuentes con texto

| Fuente | Contenido revisado y utilidad | Límite para el reto |
|---|---|---|
| PDS | Presentación del archivo y acceso a búsqueda/catálogos. Ayuda a localizar productos planetarios. | Es una portada, sin una observación concreta descargada. |
| LRO | Índice de instrumentos, archivos y herramientas de búsqueda. Permite elegir dónde buscar según la variable. | Enumerar instrumentos no verifica cobertura, resolución ni valores de un producto seleccionado. |
| Diviner | Índice EDR/RDR/derivados y nota de calidad: `tb`, columna 24, usa `-9999` para datos ausentes. | Es documentación de tratamiento de faltantes, no una temperatura medida ni evidencia de hielo. No trasladar una escala citada en la portada a todos los productos. |
| RCM | Ficha recuperada, usos de radar y acceso mediante EODMS. Explica que ciertos productos están abiertos a usuarios externos y que cada imagen tiene condiciones de uso. | No asumir que todo el archivo es accesible solo por leer una ficha pública; falta seleccionar y abrir una escena. |
| RADARSAT-1 | La ficha declara licencia abierta del archivo canadiense y enlaza recursos de imágenes. | Licencia de acceso no demuestra pertinencia para medir una propiedad de un análogo. |
| Tutorial SAR de CSA | README con rutas de trabajo en Python y QGIS. Puede reducir trabajo de integración si elegimos SAR. | No se ejecutó el tutorial ni se comprobó una medición; es material técnico, no validación del método científico. |
| Copernicus Data Space | Acceso a misiones, servicios y herramientas de exploración. | La portada y sus noticias no son un dataset de suelo, hielo o minerales. |
| University Valley | Resumen de un estudio observacional con profundidades terrestres explícitas y contexto espacial. Es la evidencia cuantitativa documental más directa de esta extracción. | Solo se recuperó el resumen; falta revisar método, datos individuales, incertidumbre y una medición planetaria comparable. |
| Mojave | Informe de ensayos terrestres de remolinos de polvo y modelado para condiciones marcianas. Aporta variables y metodología. | La parte marciana descrita es modelada, no una campaña de mediciones en Marte. La capa de texto tiene errores visibles; no extraer cifras a ciegas. |
| JETT3 | Describe el propósito de un ensayo operativo y cómo se crearon condiciones de iluminación. | No acredita que Arizona tenga iluminación lunar natural ni define una fórmula universal de selección de análogos. |
| Analog Explorer | Galería divulgativa con pares de ambientes y procesos. Sirve como antecedente de producto y guía de referencias. | Comparar imágenes no demuestra similitud cuantitativa; los detalles enlazados no se descargaron automáticamente. |

Cada ficha, URL, SHA256 y documento local aparece en [analisis_fuentes.json](analisis_fuentes.json). Los siete portales/tutoriales, los dos estudios y las dos referencias de contexto cumplen funciones distintas; no deben ponderarse como once mediciones equivalentes.

## Hallazgos documentales que sí podemos usar

**University Valley.** El resumen reporta 475 mediciones distribuidas entre cuatro valles de Quartermain; no son 475 mediciones únicamente de University Valley. Para University Valley da un intervalo de 0–98 cm hasta terreno cementado por hielo y una tendencia de 32 cm de profundidad por kilómetro a lo largo del fondo del valle. Podemos registrar esas cantidades como resultados reportados del estudio. No verificamos la tabla de datos, su incertidumbre ni una equivalencia con Phoenix. La presencia de hielo tampoco sustituye las observaciones térmicas necesarias para caracterizar permafrost. Localizador: sección Abstract, párrafo que comienza con las 475 mediciones, en el [documento extraído](../data/resultado-revisado/documents/78c732036d4e58a3.json).

**Mojave.** La página PDF 3 diferencia estudios de campo, construcción de un modelo y transformación del modelo a condiciones marcianas. La página 7 sitúa el trabajo de campo en Mojave y enumera magnitudes medidas. Esto permite separar observación terrestre de extrapolación. El texto del archivo presenta errores de reconocimiento y seis páginas sin texto: 88, 113, 114, 115, 116 y 117. No se determinaron aún cuáles son imágenes, páginas vacías o información que requiere OCR. [Documento y localizadores por página](../data/resultado-revisado/documents/0229617acb8470d0.json).

**JETT3.** La noticia relaciona el ensayo con terreno, geología y comunicaciones; también declara que las caminatas se harían de noche y se usaría un sol simulado. Esto respalda diseñar la selección según un objetivo de ensayo y distinguir condiciones naturales de condiciones instrumentadas. Localizadores: cuerpo del artículo, párrafos 2 y 6, conservados como XPath en el [documento](../data/resultado-revisado/documents/3dd78a02b731e1b7.json).

**Diviner.** La nota RDR permite diseñar una regla verificable para valores ausentes: no usar `-9999` como una temperatura real. Debemos comprobarla contra la etiqueta y documentación de la versión del producto que finalmente descarguemos. Localizador: «Note on RDR Channels 1 and 2», párrafo con `tb`, en el [documento](../data/resultado-revisado/documents/f2356e0a838fe278.json).

Estas lecturas fueron revisadas por el asistente contra los documentos locales. La revisión humana del equipo y la reproducción de cálculos siguen pendientes.

## Decisión recomendada

El extractor es útil como preparación documental. **Todavía no demuestra que un candidato terrestre resuelva el reto.** La matriz automática registra coocurrencias textuales en una muestra; no es una matriz científica validada. Un cero para Atacama, Haughton u otro sitio puede deberse a bloqueo, vocabulario, contexto en un encabezado o muestreo.

- **P0:** revisar el caso de University Valley y el método de Mojave como dos líneas documentales distintas. Elegir una sola pregunta cuando podamos abrir una muestra terrestre y una planetaria con la misma propiedad y unidades compatibles. No comparar profundidad de hielo terrestre con temperatura de Diviner como si fueran la misma variable.
- **P0:** para cualquier cifra del PDF, comprobar visualmente la tabla/página antes de usarla. Mantener unidades, localizador y alcance del modelo.
- **P1:** resolver el acceso por catálogos oficiales de los portales dinámicos y buscar copias autorizadas de Yungay/PTAL si son indispensables para la pregunta elegida.
- **P2:** ampliar el número de URLs solo si cubre una carencia concreta; obtener más portadas no es la prioridad.

## Organización y reproducibilidad

Código, pruebas, dependencias, inventario JSON, documentación técnica, certificados locales y todas las ejecuciones se encuentran en `scrapping/`. Los documentos generales del reto y `resources.txt` siguen en la raíz; `.venv` permanece allí para conservar el entorno que ya tenías activado.

Las copias históricas conservan bytes y hashes. Las rutas antiguas dentro de sus manifests son registros de procedencia históricos; los cuerpos siguen siendo reproducibles por su `source_id`. No se modificó el contenido del inventario al moverlo a `scrapping/inputs/`.

Consulta [README](../README.md) para ejecutar, renovar los certificados locales y regenerar la auditoría. La salida `resultado-revisado` se consolidó sin red a partir de tu ejecución, el reintento de las ocho fuentes y la recuperación de CSA.

Validación final: **24 pruebas aprobadas**, dependencias sin incompatibilidades y enlaces locales de la documentación comprobados. Una reproducción desde la nueva ubicación produjo archivos idénticos en los 13 documentos JSON, `evidencia.jsonl` y `cobertura.csv` (15 archivos). Dos de esos documentos son las respuestas de Earthdata/JAXA; no aumentan la cuenta de 11 fuentes con estado `extraido`.
