
# 📄 InvoiceAgent — Documentación Técnica y Flujo Completo

## 🧠 Propósito General

El **InvoiceAgent** es el agente encargado de procesar imágenes de facturas para extraer información financiera estructurada y transformarla en datos listos para generar una transacción asociada en el sistema de Kashi Finances.  
Su objetivo es **automatizar la lectura y categorización inicial** del gasto, sin comprometer la precisión ni la confirmación humana.

---

## ⚙️ Flujo General del InvoiceAgent

1. El usuario toma una foto o selecciona una imagen de factura desde la app.
2. El frontend envía esa imagen al endpoint correspondiente (`/invoices/ocr`).
3. El backend llama al **InvoiceAgent** para ejecutar OCR y estructurar los datos.
4. El **InvoiceAgent** procesa la imagen, detecta los campos relevantes y devuelve un JSON con:
   - Datos extraídos (`store_name`, `purchase_datetime`, `total_amount`, `items`, `currency`).
   - Una sugerencia de categoría (`category_suggestion`) basada en las categorías existentes del usuario.
   - Si el agente determina que la imagen no es utilizable, devuelve `status: "INVALID_IMAGE"` en lugar de datos extraídos.
  4.1. Si `status = "INVALID_IMAGE"` → el frontend muestra un mensaje para repetir foto o cancelar, y el flujo termina ahí (no hay vista previa editable, no hay commit).  
  4.2. Si `status = "DRAFT"` → se sigue al paso 5 (preview editable).
1. El frontend muestra una **pantalla de vista previa editable** donde el usuario puede revisar, corregir y confirmar los datos.
2. Al confirmar, el frontend envía los datos finales al backend mediante `/invoices/commit`.
3. El backend crea las filas correspondientes en las tablas `invoice` y `transaction`.

---

## 🧩 Estructura de la Respuesta del InvoiceAgent

#### Respuesta cuando NO se puede procesar (status: "INVALID_IMAGE")

Este estado aparece cuando el agente no puede extraer datos útiles porque:

- la imagen está demasiado borrosa / recortada,
- no es una factura (por ejemplo, foto de una mesa, del menú del restaurante, una selfie, etc.),
- el formato está demasiado roto para leerla con confianza mínima.

El agente responde:
	{
	  "status": "INVALID_IMAGE",
	  "reason": "No pude leer datos suficientes para construir la transacción. Intenta tomar otra foto donde se vea el total y el nombre del comercio."
	}

Notas:
- `reason` es texto breve y factual. Nada emocional. Nada tipo “lo siento”.
- No se devuelven campos como `store_name`, `items`, etc. porque no son confiables.
- No se guarda nada en la base de datos.

### Respuesta OCR inicial (status: "DRAFT")

El agente devuelve un objeto con la información leída de la factura:

    {
      "status": "DRAFT",
      "store_name": "Super Despensa Familiar Zona 11",
      "purchase_datetime": "2025-10-30T14:32:00-06:00",
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

Ejemplo alternativo (cuando el agente sugiere una categoría nueva que no existe aún):

    {
      "status": "DRAFT",
      "store_name": "Pet Zone",
      "purchase_datetime": "2025-10-29T18:11:00-06:00",
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

Nota: `currency` es el tipo de moneda puede ser derivado de la ubicación de la tienda. Si no se está seguro el default es "GTQ"

---

## 🧭 Especificaciones de `category_suggestion`

- `category_suggestion` siempre está presente en la primera respuesta (`status: DRAFT`).
- Sirve únicamente para **ayudar al usuario** a clasificar el gasto en la interfaz de revisión.
- El agente obtiene las categorías existentes mediante la tool `getUserCategories(user_id)`.
- Tiene dos posibles valores para `match_type`:

### match_type: "EXISTING"
Indica que el agente encontró una coincidencia con una categoría ya existente del usuario.  
El frontend debe preseleccionarla en el dropdown de categorías.

    "category_suggestion": {
      "match_type": "EXISTING",
      "category_id": "uuid-de-supermercado",
      "category_name": "Supermercado"
    }

### match_type: "NEW_PROPOSED"
Indica que el agente sugiere una nueva categoría que no existe en la cuenta del usuario.

    "category_suggestion": {
      "match_type": "NEW_PROPOSED",
      "proposed_name": "Mascotas"
    }

**Reglas adicionales:**  
- Cuando `match_type` es `"NEW_PROPOSED"`, el frontend debe seleccionar por defecto la categoría `"General"` en el dropdown.  
- El frontend debe mostrar un texto auxiliar tipo:  
  “Sugerencia: 'Mascotas'. ¿Quieres crear esta categoría nueva?”  
  junto con un botón opcional para crearla.  
- El agente **no crea categorías nuevas automáticamente**. Esto solo puede hacerlo el usuario.

---

## 🧱 Flujo del Commit Final (`/invoices/commit`)

Después de que el usuario revisa y confirma los datos, el frontend envía un cuerpo con los valores corregidos:

    {
      "user_id": "uuid",
      "invoice_data": {
        "store_name": "Super Despensa Familiar Zona 11",
        "purchase_datetime": "2025-10-30T14:32:00-06:00",
        "total_amount": 128.50,
        "currency": "GTQ",
        "items": [
          { "description": "Leche deslactosada 1L", "quantity": 2, "total_price": 35.00 },
          { "description": "Pan molde integral", "quantity": 1, "total_price": 22.50 }
        ],
        "category_id": "uuid-de-category-seleccionada"
      }
    }

El backend realiza:

1. Sube la imagen final de la factura a Supabase Storage.
2. Crea el registro en la tabla `invoice` con el `storage_path` y los metadatos relevantes.
3. Inserta la transacción asociada en `transaction`, con:
   - `category_id`: la elegida por el usuario (o “General” si no cambió nada).
   - `amount`: total de la factura.
   - `date`: fecha de compra.
   - `description`: nombre de la tienda.
   - `invoice_id`: referencia al registro de factura.

---

## 🧩 Responsabilidades del InvoiceAgent

**El InvoiceAgent debe:**

- Detectar y extraer automáticamente los datos clave de la factura.
- Estandarizar los campos (`store_name`, `purchase_datetime`, `total_amount`, `currency`).
- Construir la lista de ítems en formato estructurado.
- Consultar las categorías del usuario con la tool `getUserCategories(user_id)`.
- Proponer una categoría sugerida (`category_suggestion`), según los patrones de gasto detectados.
- No guardar nada en la base de datos.
- No crear categorías nuevas automáticamente.
- No incluir `confidence` ni `notes`.
- Responder siempre con `status: "DRAFT"` hasta que el usuario confirme.
- Si la imagen no parece una factura o es ilegible, el agente debe devolver `status: "INVALID_IMAGE"` y un campo `reason` simple.
- El agente NO debe inventar total_amount ni categoría basándose en conjeturas visuales.
- El agente NO debe intentar inferir categoría_suggestion en este caso.
- El agente NO debe devolver estructuras parciales tipo `"items": []` si realmente no pudo extraer nada útil.

---

## 💻 Responsabilidades del Frontend

**El frontend debe:**

- Enviar la imagen al endpoint `/invoices/ocr` para procesarla.
- Mostrar los campos devueltos por el agente en una pantalla de **edición previa a guardar**.
- Permitir al usuario editar libremente los campos (`store_name`, `purchase_datetime`, `total_amount`, `items`, `category_id`).
- Mostrar un dropdown con todas las categorías del usuario (incluyendo `"General"`).
- Si `match_type = "EXISTING"`, preseleccionar esa categoría en el dropdown.
- Si `match_type = "NEW_PROPOSED"`, seleccionar `"General"` por defecto y mostrar el botón para crear la categoría sugerida.
- Al confirmar, enviar los datos finales corregidos a `/invoices/commit`.
- Si el usuario cancela, no se guarda nada en la base de datos.
- No mostrar texto de confianza ni explicaciones del OCR.
- No interpreta ni modifica la lógica del agente, solo presenta y recolecta la información.
- Si la respuesta del endpoint `/invoices/ocr` viene con  
`"status": "INVALID_IMAGE"`:
	  - El frontend debe mostrar un mensaje genérico fijo, por ejemplo:
	     - "No pudimos leer la factura. Intenta tomar otra foto donde se vea claramente el total y el nombre del comercio."
	  - Debe ofrecer dos acciones:
	     - “Volver a intentar” (abrir cámara / selector de imagen de nuevo)
	     - “Cancelar”
	  - Importante: En este estado NO se muestra la pantalla de edición previa, porque no hay datos qué editar.
	  - Nada se manda a `/invoices/commit`.

---

## 🧾 Implicaciones en la Base de Datos

**invoice**
- Guarda la imagen y la versión textual procesada (campo `extracted_text`).
- No guarda la categoría ni las sugerencias del agente.
- Campos principales:
  - `id UUID PK`
  - `user_id UUID FK → auth.users.id`
  - `storage_path TEXT`
  - `extracted_text TEXT`
  - `created_at TIMESTAMPTZ DEFAULT now()`
  - `updated_at TIMESTAMPTZ DEFAULT now()`

**transaction**
- Guarda la información financiera confirmada por el usuario.
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
- La categoría se guarda solo en `transaction`, nunca en `invoice`.
- La categoría `"General"` siempre está disponible por defecto en todas las cuentas.
- Si el usuario no selecciona otra, esa es la categoría que se asocia a la transacción.
- Cuando la respuesta del agente es `INVALID_IMAGE`, no se crea ningún registro en `invoice` ni `transaction`.
    
- No se sube nada a Supabase Storage porque aún no hay confirmación humana ni datos válidos.
    
- Esto mantiene la promesa de “no guardamos nada sin tu permiso” y también evita basura en la base de datos (facturas borrosas, fotos accidentales, etc.).

---

## 🚀 Resumen

- El **InvoiceAgent** automatiza la extracción y preclasificación de facturas.
- El agente **solo sugiere**, el usuario **siempre confirma**.
- El frontend es la capa de revisión y validación.
- No se crean categorías automáticamente.
- No se guarda nada hasta que el usuario confirma.
- La categoría final se guarda en `transaction.category_id`.

Este diseño garantiza una experiencia fluida y confiable, manteniendo al usuario siempre en control del proceso de registro de gastos.
