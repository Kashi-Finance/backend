# 📄 InvoiceAgent — Documentación Técnica y Flujo Completo

## 🧠 Propósito General

**InvoiceAgent** es un **workflow de extracción multimodal single-shot** que procesa imágenes de facturas para extraer información financiera estructurada. Su objetivo es **automatizar la lectura y categorización inicial** del gasto, sin comprometer la precisión ni la confirmación humana.

**Características técnicas:**
- **Single-shot LLM workflow**: Una sola llamada a Gemini con todo el contexto
- **Multimodal vision**: Usa capacidades nativas de Gemini para leer imágenes directamente
- **No tools / No ADK**: Todo el contexto se pasa en el prompt (categorías, perfil, imagen)
- **Determinístico**: Temperature=0.0 para extracciones consistentes
- **Structured output**: JSON schema forzado via `response_mime_type="application/json"`
- **RLS enforced**: Usa `get_supabase_client` con JWT token del usuario para todas las operaciones

---

## ⚙️ Flujo General del InvoiceAgent

1. El usuario toma una foto o selecciona una imagen de factura desde la app.
2. El frontend envía esa imagen al endpoint `POST /invoices/ocr`.
3. El backend:
   - Valida el token JWT del usuario (RLS)
   - Obtiene perfil del usuario (`get_user_profile`) para country y currency_preference
   - Obtiene categorías del usuario (`get_user_categories`) vía authenticated Supabase client
4. El backend llama a `run_invoice_agent()` con:
   - Base64 de la imagen **REQUERIDO**
   - Contexto completo: user_id, categorías, perfil
5. El **InvoiceAgent** hace UNA llamada a Gemini que:
   - Lee la imagen usando capacidades de vision nativa
   - Extrae campos estructurados (store_name, total, items, etc.)
   - Sugiere categoría (EXISTING o NEW_PROPOSED)
   - Devuelve JSON con status DRAFT, INVALID_IMAGE, o OUT_OF_SCOPE
6. El backend mapea la respuesta del agente a `InvoiceOCRResponseDraft` o `InvoiceOCRResponseInvalid`
7. **IMPORTANTE: La imagen NO se sube a Supabase Storage en esta fase.** Solo se procesa en memoria.
8. El frontend:
   - Si `status = "INVALID_IMAGE"` → muestra mensaje de error, permite reintentar
   - Si `status = "DRAFT"` → muestra pantalla de vista previa editable con los datos extraídos
9. Al confirmar, el frontend envía los datos finales mediante `POST /invoices/commit` incluyendo:
   - Datos editados por el usuario
   - La imagen original como base64
   - account_id y category_id seleccionados
10. El backend en el commit:
    - **AHORA sí sube la imagen a Supabase Storage** (solo después de confirmación humana)
    - Crea la fila en `invoice` con `extracted_text` canónico y el storage_path real en columna separada
    - Crea la fila en `transaction` con la categoría elegida
    - Ambas operaciones usan RLS para asegurar que `user_id = auth.uid()`

---

## 🧩 Estructura de la Respuesta del InvoiceAgent

### Respuesta cuando NO se puede procesar (status: "INVALID_IMAGE")

Este estado aparece cuando el agente no puede extraer datos útiles porque:

- la imagen está demasiado borrosa / recortada,
- no es una factura (por ejemplo, foto de una mesa, del menú del restaurante, una selfie, etc.),
- el formato está demasiado roto para leerla con confianza mínima.

El agente responde:
```json
{
  "status": "INVALID_IMAGE",
  "reason": "No pude leer datos suficientes para construir la transacción. Intenta tomar otra foto donde se vea el total y el nombre del comercio."
}
```

Notas:
- `reason` es texto breve y factual. Nada emocional. Nada tipo "lo siento".
- No se devuelven campos como `store_name`, `items`, etc. porque no son confiables.
- No se guarda nada en la base de datos.

### Respuesta OCR inicial (status: "DRAFT")

El agente devuelve un objeto con la información leída de la factura:

```json
{
  "status": "DRAFT",
  "store_name": "Super Despensa Familiar Zona 11",
  "transaction_time": "2025-10-30T14:32:00-06:00",
  "total_amount": 128.50,
  "currency": "GTQ",
  "items": [
    { "description": "Leche deslactosada 1L", "quantity": 2, "unit_price": 17.50, "total_price": 35.00 },
    { "description": "Pan molde integral", "quantity": 1, "unit_price": 22.50, "total_price": 22.50 },
    { "description": "Huevos docena AA", "quantity": 1, "unit_price": 71.00, "total_price": 71.00 }
  ],
  "category_suggestion": {
    "match_type": "EXISTING",
    "category_id": "uuid-de-supermercado",
    "category_name": "Supermercado"
  }
}
```

Ejemplo alternativo (cuando el agente sugiere una categoría nueva que no existe aún):

```json
{
  "status": "DRAFT",
  "store_name": "Pet Zone",
  "transaction_time": "2025-10-29T18:11:00-06:00",
  "total_amount": 312.00,
  "currency": "GTQ",
  "items": [
    { "description": "Concentrado premium perro 15kg", "quantity": 1, "unit_price": 312.00, "total_price": 312.00 }
  ],
  "category_suggestion": {
    "match_type": "NEW_PROPOSED",
    "proposed_name": "Mascotas"
  }
}
```

Nota: `currency` es el tipo de moneda puede ser derivado de la ubicación de la tienda. Si no se está seguro el default es "GTQ"

---

## 🧭 Especificaciones de `category_suggestion`

**ESTRUCTURA UNIFORME (todos los campos siempre presentes):**

La respuesta `category_suggestion` SIEMPRE incluye estos 4 campos:
- `match_type`: "EXISTING" | "NEW_PROPOSED" (discriminador)
- `category_id`: string | null
- `category_name`: string | null
- `proposed_name`: string | null

**Esto permite:**
- Frontend (Flutter) puede usar tipado estático predecible
- Backend puede validar la invariante (reglas de nulidad)
- Menos checks defensivos en el cliente (no verificar existencia de claves)
- Respuestas malformadas se detectan en validación

**INVARIANTE (OBLIGATORIO):**

1. Si `match_type = "EXISTING"`:
   - `category_id` ≠ null (UUID exacto de lista de categorías del usuario)
   - `category_name` ≠ null (nombre exacto de esa categoría)
   - `proposed_name` = null

2. Si `match_type = "NEW_PROPOSED"`:
   - `category_id` = null
   - `category_name` = null
   - `proposed_name` ≠ null (nombre sugerido)

El backend valida esta invariante y rechaza respuestas incorrecto.

**Ejemplos:**

EXISTING:
```json
"category_suggestion": {
  "match_type": "EXISTING",
  "category_id": "uuid-de-supermercado",
  "category_name": "Supermercado",
  "proposed_name": null
}
```

NEW_PROPOSED:
```json
"category_suggestion": {
  "match_type": "NEW_PROPOSED",
  "category_id": null,
  "category_name": null,
  "proposed_name": "Mascotas"
}
```

---

## 🔧 Implementación Técnica

### Herramientas del Agente (Backend)

El backend llama estas funciones ANTES de invocar al workflow de InvoiceAgent:

1. **`get_user_profile(supabase_client, user_id)`**
   - Obtiene: country, currency_preference, locale
   - Usa authenticated Supabase client (RLS enforced)
   - Fallback: defaults para Guatemala si no existe perfil

2. **`get_user_categories(supabase_client, user_id)`**
   - Obtiene categorías del usuario + categorías del sistema
   - Query: `flow_type = 'outcome' AND (user_id = {user_id} OR user_id IS NULL)`
   - Usa authenticated Supabase client (RLS enforced)
   - Formato de salida: `[{"id": "uuid", "name": "Nombre"}]`

### Detección de MIME Type

El agente detecta automáticamente el tipo de imagen del base64:
- `/9j/` → `image/jpeg`
- `iVBORw0KGgo` → `image/png`
- `R0lGOD` → `image/gif`
- `UklGR` → `image/webp`
- Default: `image/jpeg`

---

## 🧱 Flujo del Commit Final (`POST /invoices/commit`)

Después de que el usuario revisa y confirma los datos, el frontend envía un cuerpo con los valores corregidos y la imagen original:

```json
{
  "store_name": "Super Despensa Familiar Zona 11",
  "transaction_time": "2025-10-30T14:32:00-06:00",
  "total_amount": 128.50,
  "currency": "GTQ",
  "purchased_items": "- Leche deslactosada 1L (2x) @ Q17.50 = Q35.00\n- Pan molde integral @ Q22.50 = Q22.50",
  "image_base64": "/9j/4AAQSkZJRgABAQEAYABgAAD...",
  "image_filename": "receipt_20251030.jpg",
  "account_id": "uuid-de-cuenta",
  "category_id": "uuid-de-categoria"
}
```

El backend realiza (EN ESTE ORDEN):

1. **Decodifica y sube la imagen a Supabase Storage**
   - Recibe image_base64 del frontend
   - Lo decodifica a bytes
   - Lo sube a Supabase Storage con path: `invoices/{user_id}/{uuid}`
   - Obtiene el storage_path real

2. **Crea el registro en la tabla `invoice` con**
   - `user_id` (del token JWT)
   - `storage_path` (el path real donde se guardó la imagen)
   - `extracted_text` (formato canónico con todos los detalles)

3. **Inserta la transacción asociada en `transaction`, con**
   - `category_id`: la elegida por el usuario (o sugerida)
   - `amount`: total de la factura
   - `date`: fecha de compra
   - `description`: nombre de la tienda
   - `invoice_id`: referencia al registro de factura creado

**Nota importante**: Si el usuario cancela antes de hacer commit, la imagen NO se sube a storage y NO se crea ningún registro en la base de datos. Solo se procesa en memoria durante la fase draft.

---

## 🧩 Responsabilidades del InvoiceAgent

**El InvoiceAgent debe:**

- Detectar y extraer automáticamente los datos clave de la factura
- Estandarizar los campos (`store_name`, `transaction_time`, `total_amount`, `currency`)
- Construir la lista de ítems en formato estructurado
- Proponer una categoría sugerida (`category_suggestion`) basándose en las categorías proporcionadas
- Devolver JSON con el schema exacto esperado
- Si la imagen no parece una factura o es ilegible, devolver `status: "INVALID_IMAGE"` y un campo `reason`
- NO guardar nada en la base de datos
- NO crear categorías nuevas automáticamente
- NO inventar IDs de categorías

**El InvoiceAgent NO debe:**

- Inventar `total_amount` ni categoría basándose en conjeturas visuales
- Intentar inferir `category_suggestion` si la imagen es INVALID_IMAGE
- Devolver estructuras parciales tipo `"items": []` si realmente no pudo extraer nada útil
- Llamar tools o funciones externas (todo el contexto viene en el prompt)

---

## 💻 Responsabilidades del Frontend

**El frontend debe:**

- Enviar la imagen al endpoint `POST /invoices/ocr` para procesarla
- Mostrar los campos devueltos por el agente en una pantalla de **edición previa a guardar**
- Permitir al usuario editar libremente los campos
- Mostrar un dropdown con todas las categorías del usuario (incluyendo `"General"`)
- Si `match_type = "EXISTING"`, preseleccionar esa categoría en el dropdown
- Si `match_type = "NEW_PROPOSED"`, seleccionar `"General"` por defecto y mostrar botón para crear categoría
- Al confirmar, enviar los datos finales corregidos a `POST /invoices/commit`
- Si el usuario cancela, no se guarda nada en la base de datos
- Si `status = "INVALID_IMAGE"`:
  - Mostrar mensaje genérico: "No pudimos leer la factura. Intenta tomar otra foto donde se vea claramente el total y el nombre del comercio."
  - Ofrecer: "Volver a intentar" o "Cancelar"
  - NO mostrar pantalla de edición
  - NO enviar nada a `/invoices/commit`

---

## 🧾 Implicaciones en la Base de Datos

**invoice**
- Guarda la imagen y la versión textual procesada (campo `extracted_text`)
- No guarda la categoría ni las sugerencias del agente
- Campos principales:
  - `id UUID PK`
  - `user_id UUID FK → auth.users.id`
  - `storage_path TEXT`
  - `extracted_text TEXT` (formato canónico)
  - `created_at TIMESTAMPTZ DEFAULT now()`
  - `updated_at TIMESTAMPTZ DEFAULT now()`

**transaction**
- Guarda la información financiera confirmada por el usuario
- Campos relevantes:
  - `id UUID PK`
  - `user_id UUID FK → auth.users.id`
  - `account_id UUID FK → account.id`
  - `category_id UUID FK → category.id NULLABLE`
  - `invoice_id UUID FK → invoice.id NULLABLE`
  - `flow_type TEXT CHECK in (income, outcome)`
  - `amount NUMERIC(12,2)`
  - `date TIMESTAMPTZ`
  - `description TEXT`
  - `created_at TIMESTAMPTZ DEFAULT now()`
  - `updated_at TIMESTAMPTZ DEFAULT now()`

**Notas de diseño:**
- La categoría se guarda solo en `transaction`, nunca en `invoice`
- La categoría `"General"` siempre está disponible por defecto
- Si el usuario no selecciona otra, esa es la categoría que se asocia a la transacción
- Cuando la respuesta del agente es `INVALID_IMAGE`, no se crea ningún registro en `invoice` ni `transaction`
- **La imagen SOLO se sube a Supabase Storage cuando el usuario hace commit** (no en el draft)
- Si el usuario cancela antes de commit, la imagen nunca se persiste en storage

---

## 🚀 Resumen

- El **InvoiceAgent** automatiza la extracción y preclasificación de facturas usando vision AI
- El agente **solo sugiere**, el usuario **siempre confirma**
- Implementado como workflow single-shot (no ADK, no tools)
- El frontend es la capa de revisión y validación
- No se crean categorías automáticamente
- No se guarda nada hasta que el usuario confirma
- La categoría final se guarda en `transaction.category_id`
- RLS enforced en todas las operaciones de base de datos

Este diseño garantiza una experiencia fluida y confiable, manteniendo al usuario siempre en control del proceso de registro de gastos.
