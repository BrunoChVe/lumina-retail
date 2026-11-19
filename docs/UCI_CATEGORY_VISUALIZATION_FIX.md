# Corrección y Diagnóstico del Gráfico de Categorías UCI Online Retail (GBP)

**Proyecto:** LUMINA Retail (RetailSmart Data Platform)  
**Módulo:** Commercial Intelligence (`Commercial.jsx`)  
**Fecha:** Noviembre 2026  
**Autor:** Bruno Chihuán Velásquez  
**Estado:** Resuelto y Publicado bajo Gobernanza WAP-02.1  

---

## 1. Diagnóstico de Extremo a Extremo y Causa Raíz

### 1.1. Síntoma Reportado
En el módulo comercial de LUMINA Retail, el gráfico *"Participación y ventas por categoría de producto"* presentaba barras para Olist (BRL) y TheLook (USD), pero el bloque correspondiente a UCI Online Retail (GBP) aparecía vacío, a pesar de que la fuente registraba un total de 10,666,684.54 GBP en ventas históricas.

### 1.2. Análisis de Extremo a Extremo
Se inspeccionó cada capa del flujo de datos:
1. **Tabla Gold `gold_commercial_categories` en BigQuery:**
   Al consultar los registros para UCI bajo la versión publicada activa (`run_id = run_commercial_20261119061142_dabb04`), se evidenció que existía una única fila con:
   ```json
   {
     "source_system": "uci",
     "currency_code": "GBP",
     "category_type": "No_Taxonomy",
     "category": null,
     "category_rank": 1,
     "total_sales": 10666684.54,
     "sales_share_pct": 100.0
   }
   ```
2. **Script de Escritura WAP (`03a_wap_write_commercial.sql`):**
   El pipeline original insertaba explícitamente `CAST(NULL AS STRING) AS category` y `"No_Taxonomy" AS category_type`, agrupando la totalidad de los 5,660,981 artículos vendidos en un único registro sin taxonomía.
3. **Script de Auditoría WAP (`04a_wap_audit_commercial.sql`):**
   La prueba `TEST_COMM_UCI_NO_INVENTED_CATEGORIES` forzaba que `category IS NOT NULL` tuviera un conteo de 0 filas, obligando a que `category` permaneciera como `NULL` para evitar que el pipeline WAP abortara la transacción.
4. **Endpoint REST FastAPI (`/api/commercial/categories`):**
   Retornaba el registro con `"category": null`.
5. **Componente Frontend (`Commercial.jsx`) y Recharts:**
   El gráfico de barras horizontales utilizaba `<YAxis type="category" dataKey="category" />`. Al recibir `category: null`, la biblioteca Recharts no podía computar el dominio ni el tick del eje vertical para una clave nula, provocando que no se dibujara ninguna barra ni etiqueta visible en pantalla.

### 1.3. Causa Raíz Consolidada
La ausencia de datos en el gráfico se debió a una cascada de diseño: la ausencia de una taxonomía nativa en los datos originales de UCI llevó a forzar `category = NULL` tanto en la escritura como en la auditoría WAP, lo cual provocó la falla silenciosa del renderizador categórico de Recharts en el frontend.

---

## 2. Reglas de Negocio y Clasificación Derivada

Siguiendo las restricciones del proyecto para evitar la invención arbitraria de datos, se implementó una estrategia transparente y determinista basada en el campo textual `Description` (`product_name`) de UCI:

1. **Catálogo de 7 Categorías Derivadas (`DERIVED_RULE`):**
   - **Kitchen & Dining:** Palabras clave `CAKE`, `BAKING`, `TEA`, `MUG`, `COFFEE`, `PLATE`, `BOWL`, `KITCHEN`, `CUTLERY`, `JUG`, `PANTRY`, `JAM`, `JAR`, `GLASS`, `BOTTLE`, `LUNCH BOX`, `LUNCH BAG`, `FORK`, `SPOON`, `DISH`, `COOK`.
   - **Home Decor & Lighting:** Palabras clave `LIGHT`, `LAMP`, `CANDLE`, `T-LIGHT`, `HOLDER`, `FRAME`, `CLOCK`, `MIRROR`, `WALL`, `DOORMAT`, `SIGN`, `CUSHION`, `ORNAMENT`, `DECORATION`, `CHANDELIER`.
   - **Seasonal & Party:** Palabras clave `CHRISTMAS`, `XMAS`, `PARTY`, `BUNTING`, `BALLOON`, `EASTER`, `HALLOWEEN`, `SNOWFLAKE`, `BIRTHDAY`, `GARLAND`.
   - **Bags & Luggage:** Palabras clave `BAG`, `PURSE`, `WALLET`, `TOTE`, `SHOPPER`, `SUITCASE`, `LUGGAGE`, `BACKPACK`.
   - **Stationery & Crafts:** Palabras clave `PAPER`, `CARD`, `NOTEBOOK`, `PEN`, `PENCIL`, `STICKER`, `CRAFT`, `RIBBON`, `WRAP`, `ALBUM`, `BOOK`.
   - **Gifts & Toys:** Palabras clave `HEART`, `RETROSPOT`, `VINTAGE`, `TOY`, `GAME`, `PLUSH`, `TEDDY`, `TRINKET`, `DOLL`, `MAGIC`, `PUZZLE`.
   - **Postage & Fees:** Palabras clave `POSTAGE`, `MANUAL`, `CARRIAGE`, `DISCOUNT`, `FEE`.
2. **Categoría de Respaldo Transparente (`UNCLASSIFIED`):**
   - Todo producto cuya descripción no coincida con ninguna de las 7 reglas se cataloga explícitamente como **`Unclassified`** con `category_origin = 'UNCLASSIFIED'`.
   - No se descarta ninguna venta ni se imputan categorías espurias.

---

## 3. Resultados de Conciliación Matemática

Se verificó la conciliación matemática exacta entre la capa Silver (`stg_uci_online_retail`) y la capa Gold (`gold_commercial_categories`):

| Rank | Categoría | Origen Taxonomía | Productos Únicos | Unidades Vendidas | Órdenes | Ventas Totales (GBP) | Participación (%) |
|:---:|---|:---:|---:|---:|---:|---:|---:|
| **1** | Kitchen & Dining | `DERIVED_RULE` | 703 | 1,341,297 | 15,908 | £2,739,368.58 | 25.68 % |
| **2** | Home Decor & Lighting | `DERIVED_RULE` | 832 | 1,196,993 | 15,518 | £2,358,680.24 | 22.11 % |
| **3** | Unclassified | `UNCLASSIFIED` | 1,593 | 1,088,292 | 16,107 | £1,953,633.04 | 18.32 % |
| **4** | Gifts & Toys | `DERIVED_RULE` | 318 | 440,669 | 11,761 | £805,164.23 | 7.55 % |
| **5** | Bags & Luggage | `DERIVED_RULE` | 169 | 434,007 | 8,380 | £790,415.93 | 7.41 % |
| **6** | Stationery & Crafts | `DERIVED_RULE` | 397 | 676,850 | 10,554 | £781,648.06 | 7.33 % |
| **7** | Seasonal & Party | `DERIVED_RULE` | 260 | 436,053 | 9,676 | £763,112.67 | 7.15 % |
| **8** | Postage & Fees | `DERIVED_RULE` | 34 | 46,820 | 4,054 | £474,661.79 | 4.45 % |
| **TOTAL** | **8 Categorías** | — | **3,941** | **5,660,981** | **20,728** | **£10,666,684.54** | **100.00 %** |

### Resumen de Cobertura
- **Ventas Clasificadas (`DERIVED_RULE`):** £8,713,051.50 (**81.68 %** del total).
- **Ventas Sin Clasificar (`UNCLASSIFIED`):** £1,953,633.04 (**18.32 %** del total).
- **Discrepancia financiera:** **£0.00** (conciliación al 100.000 %).

---

## 4. Cambios Técnicos Implementados

1. **`scripts/wap/03a_wap_write_commercial.sql`:**
   - Se reemplazó la inserción estática de `category = NULL` por una subconsulta con `CASE` sobre expresiones regulares.
   - Se calcularon `items_sold`, `distinct_products`, `orders`, `total_sales`, `avg_item_price` y `sales_share_pct` por cada categoría.
   - Se enriqueció `gold_commercial_products` asignando la categoría correspondiente a cada uno de los productos de UCI.
2. **`scripts/wap/04a_wap_audit_commercial.sql`:**
   - Se actualizó la prueba `TEST_COMM_UCI_NO_INVENTED_CATEGORIES` para auditar que no existan valores `NULL` ni categorías fuera de la lista documentada, y que `category_type` sea estrictamente `DERIVED_RULE` o `UNCLASSIFIED`.
3. **`backend/app/main.py`:**
   - En `/api/commercial/categories`, se expusieron `category_type` y `category_origin` con fallback `COALESCE(category, 'Unclassified')`.
   - En `/api/commercial/products`, se añadió `COALESCE(category, 'Unclassified') AS category`.
4. **`frontend/src/pages/Commercial.jsx`:**
   - Se añadió un panel informativo en el bloque UCI con badges distintivos de categorías derivadas y sin clasificar.
   - Se incluyó una tabla de desglose con métricas por categoría (Rank, Unidades, Productos únicos, Ventas y % Participación).
   - Se implementó un cálculo de altura dinámico en Recharts para garantizar que las 8 barras se rendericen con holgura y etiquetas legibles.
   - Se garantizó que cada fuente mantenga su escala y divisa nativa (Olist BRL, TheLook USD, UCI GBP).
   - Se añadió protección contra bloques vacíos si una fuente no tiene registros.

---

## 5. Publicación WAP y Rollback

La versión fue publicada de manera atómica siguiendo el protocolo WAP-02.1:
- **ID de Publicación Activa:** `run_commercial_20261119085528_c222ee`
- **ID de Publicación Anterior (Preservada para Rollback):** `run_commercial_20261119061142_dabb04`
- **Fencing Token:** 2 (monotónico anti-zombie)
- **Estado de Auditorías:** 6 de 6 auditorías aprobadas al 100%.

---

## 6. Pruebas Automatizadas y Validación

Se amplió la suite de pruebas en `backend/tests/test_api.py`:
1. `test_commercial_categories`: Valida la presencia de las 8 categorías de UCI, tipos `DERIVED_RULE`/`UNCLASSIFIED`, moneda GBP y no regresión de Olist (15) y TheLook (15).
2. `test_uci_categories_reconciliation_and_coverage`: Valida que el 81.68% de las ventas estén clasificadas y el 18.32% en Unclassified, totalizando 100%.
3. `test_uci_null_and_single_category_robustness`: Simula escenarios de categorías nulas o fuentes de categoría única.

**Resultado de Pruebas:**
- Pruebas de API y Negocio: **38 / 38 superadas (100 %)**
- Pruebas de Aceptación WAP: **17 / 17 superadas (100 %)**
- Total suite del proyecto: **55 / 55 pruebas aprobadas exitosamente.**
