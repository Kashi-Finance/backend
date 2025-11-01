# Kashi Finances — Documentación de la Arquitectura de Agentes de Recomendaciones

## 🧠 Propósito General

El módulo de **Agentes de Recomendaciones** de Kashi Finances tiene como propósito principal ofrecer sugerencias personalizadas de productos, metas o alternativas financieras que se ajusten al presupuesto y preferencias del usuario.  
A diferencia de otros agentes del ecosistema, este subsistema está completamente orientado a **asistir al usuario en decisiones de compra o planeación financiera**, sin procesar facturas ni registrar transacciones.

El sistema está compuesto por un conjunto de agentes especializados que trabajan de forma colaborativa bajo una arquitectura **orquestada y modular**, diseñada para ser escalable y segura. Toda la arquitectura sigue la premisa **"un solo punto de entrada"**: el **agente verificador (RecommendationCoordinatorAgent)** funge como **orquestador central** que coordina subagentes especializados y decide el flujo de acción.

---

## 🧩 Componentes Principales

### 1. RecommendationCoordinatorAgent (Orquestador)

El **RecommendationCoordinatorAgent** es el núcleo del sistema. Su función principal es **coordinar la interacción entre los subagentes**, interpretando la solicitud del usuario y determinando el flujo correcto del proceso.  

#### Responsabilidades:
- Actúa como orquestador y verificador.
- Analizar la entrada del usuario (`query_raw`) y determinar si se trata de lenguaje **natural** o **técnico**.
- **Filtro de intención y cumplimiento**
	- Evalúa si la solicitud describe un producto o meta de compra legítima.
	- Rechaza solicitudes relacionadas con contenido sexual explícito, actividad criminal, daño físico o venta de artículos regulados.
	- Si la intención es inválida o prohibida → responde `NO_VALID_OPTION` y NO invoca a subagentes.
- Si la intención es poco clara pero potencialmente válida → responde `NEEDS_CLARIFICATION` con una pregunta dirigida tipo “¿Qué producto específico estás buscando?”.
- Validar si existen campos faltantes antes de iniciar la búsqueda.
- Orquestar las llamadas a los subagentes `SearchAgent` y `FormatterAgent`.
- Traducir peticiones en lenguaje natural a especificaciones técnicas estándar (por ejemplo, convertir “quiero una laptop para diseño” en requisitos de RAM, GPU y pantalla).
- Consolidar las respuestas finales y devolver un JSON estructurado al frontend con un estado (`status`) y posibles resultados.
- Mantener la comunicación a través del endpoint `/recommendations/query`.
- Pasa los campos `user_note` y `preferred_store` como contexto a **SearchAgent** y **FormatterAgent**. Ambos agentes deben usarlos para adaptar sus resultados y formato.

#### Estados posibles:
- `NEEDS_CLARIFICATION`: faltan datos para ejecutar la búsqueda.
- `OK`: resultados válidos encontrados.
- `NO_VALID_OPTION`: no se encontraron opciones confiables.

---

### 2. SearchAgent (Agente de Búsqueda)

El **SearchAgent** realiza la búsqueda activa de productos, servicios o metas que coincidan con los criterios definidos por el orquestador.

#### Responsabilidades:
- Buscar hasta **tres opciones reales** que coincidan con la descripción (`query_raw`), presupuesto (`budget_hint`), país (`getUserCountry`), tienda preferida (`preferred_store`) y notas o aclaraciones del usuario (`user_note`).
- Retornar datos **estructurados** sin interpretación:
  - `product_title`
  - `price_total`
  - `seller_name`
  - `url`
  - `pickup_available`
  - `warranty_info`
- Evitar URLs falsas, precios inventados o fuentes no verificables.
- Usa `user_note` (si no es null) para filtrar resultados que contradigan las preferencias del usuario. Ejemplo: excluir resultados con “RGB” si el `user_note` contiene “nada gamer”.
- Retornar `error: true` si no encuentra datos confiables.

#### Entrada esperada:
```json
{
  "query_raw": "laptop para diseño gráfico",
  "budget_hint": 7000,
  "country": "GT",
  "preferred_store": "Intelaf",
  "user_note": "nada gamer con luces RGB"
}
```

#### Salida típica:
```json
{
  "results": [
    {
      "product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD",
      "price_total": 6200.00,
      "seller_name": "ElectroCentro Guatemala",
      "url": "https://electrocentro.gt/hp-envy-ryzen7",
      "pickup_available": true,
      "warranty_info": "Garantía HP 12 meses"
    }
  ]
}
```

---

### 3. FormatterAgent (Agente de Formateo)

El **FormatterAgent** recibe los datos del **SearchAgent** y los valida, limpia y transforma en resultados finales listos para mostrar al usuario.

#### Responsabilidades:
- Eliminar resultados sospechosos o inconsistentes.
- Verificar coherencia entre los precios y el presupuesto (`budget_hint`).
- Aplicar el contexto del usuario (`user_note`, `preferred_store`).
- Generar campos amigables para la interfaz de usuario:
  - `copy_for_user`: texto explicativo muy breve.
  - `badges`: etiquetas visuales (máximo 3) como “Más barata” o “Garantía 12 meses”.
- Mantener la voz de marca y evitar lenguaje promocional o subjetivo.

#### Reglas de redacción de `copy_for_user`:
- Tono informativo, confiable y sin exageraciones.
- Máximo 3 oraciones.
- No usar emojis ni frases subjetivas (“es perfecta para ti”).
- Puede mencionar diferencias reales (precio, garantía, disponibilidad inmediata).

#### Ejemplo de salida final:
```json
{
  "status": "OK",
  "results_for_user": [
    {
      "product_title": "ASUS Vivobook 15 Ryzen 7 16GB 512GB SSD",
      "price_total": 6750.00,
      "seller_name": "TecnoMundo Guatemala",
      "url": "https://tecnomundo.com.gt/asus-vivobook15-ryzen7",
      "pickup_available": true,
      "warranty_info": "Garantía 12 meses tienda",
      "copy_for_user": "Ideal para Photoshop y diseño gráfico. Cumple con GPU dedicada y diseño sobrio sin luces gamer.",
      "badges": ["Buen rendimiento", "Diseño sobrio", "GPU dedicada"]
    }
  ]
}
```

---

### 4. getUserCountry (Tool Auxiliar)

Herramienta utilizada por los subagentes para determinar el país del usuario y adaptar los resultados a su contexto.

#### Funciones:
- Consultar el país desde la tabla `profile`.
- Si no hay información disponible, retorna `GT` como valor por defecto.
- Permite que las búsquedas sean **locales y contextualmente relevantes**.

---

## ⚙️ Flujo Completo de Ejecución

1. El usuario inicia una búsqueda mediante `/recommendations/query`.
2. El **RecommendationCoordinatorAgent** evalúa el tipo de lenguaje (técnico o natural).
3. Si es inválida → `NO_VALID_OPTION`.
4. Si faltan datos → `NEEDS_CLARIFICATION`.
5. Si la información está completa → llama a **SearchAgent**.
6. **SearchAgent** busca y devuelve resultados crudos.
7. **FormatterAgent** valida, filtra y genera el texto final para la interfaz.
8. El orquestador devuelve al frontend el `status` final con los resultados formateados.

---

## 🗄️ Estructura de Persistencia

### Tabla `wishlist`
Representa la meta o intención de compra.

Campos:
- `user_id`
- `goal_title` (texto original del usuario)
- `budget_hint`
- `preferred_store`
- `user_note`
- `status` inicial `'active'`
- timestamps

### Tabla `wishlist_item`
Guarda los productos sugeridos que el usuario decide conservar.

Campos:
- `wishlist_id`
- `product_title`
- `price_total`
- `seller_name`
- `url`
- `pickup_available`
- `warranty_info`
- `copy_for_user`
- `badges`

---

## 🧠 Política de Voz y Tono

El texto generado por el **FormatterAgent** define la voz visible de Kashi Finances:
- Tono informativo, profesional y breve.
- Sin lenguaje promocional.
- Claridad ante todo.
- Los mensajes del agente son finales: el frontend no los modifica.

---

## 🚀 Extensiones Futuras

- **InsightAgent**: análisis de hábitos de consumo para ofrecer sugerencias de ahorro.
- **PriceTrackerAgent**: seguimiento de variaciones de precios de productos guardados.
- **BudgetAdvisor**: asesor inteligente de presupuesto vinculado con metas y gastos.

---

## 📘 Conclusión

La arquitectura de los **Agentes de Recomendaciones** permite a Kashi Finances ofrecer una experiencia integral y coherente en la toma de decisiones financieras.  
El modelo orquestado mediante el **RecommendationCoordinatorAgent** garantiza que las búsquedas, validaciones y resultados finales se ejecuten de manera eficiente, escalable y segura.

