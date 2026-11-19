# Auditoría de Tiendas y Regiones (Limitaciones Documentadas)

## Estado de las Fuentes de Datos

Se realizó una inspección a las tres fuentes (Olist, TheLook y UCI Online Retail) con el fin de identificar las "tres tiendas físicas", "ocho regiones logísticas" y "doce unidades de negocio" requeridas en el documento operativo original.

### 1. TheLook eCommerce (USD)
- Posee 10 `distribution_centers` (centros de distribución en EEUU: Mobile AL, New Orleans LA, etc.). No están documentados como "3 tiendas".

### 2. Olist Store (BRL)
- Posee miles de vendedores (`seller_id`) distribuidos por estados y ciudades en Brasil. No agrupa las operaciones en "3 tiendas físicas" del retailer, ya que es un modelo de marketplace descentralizado.

### 3. UCI Online Retail (GBP)
- Posee datos transaccionales asociados a clientes y países (mayoritariamente Reino Unido y Europa). No existe atributo de tienda o centro de distribución.

## Limitación Comprobada
**No existe una relación verificable directa** en los datos transaccionales con 3 tiendas físicas, 8 regiones y 12 unidades de negocio de un único retailer unificado.

## Diseño Dimensional Propuesto (Modelo Genérico)
Dado el requerimiento de implementar vistas analíticas y ante la imposibilidad de "inventar" relaciones, se propone el siguiente mapeo lógico que asimila las fuentes a unidades lógicas para habilitar el modelo dimensional:

- **Dimensión Tienda (`dim_store`):**
  1. Olist Marketplace (Brasil)
  2. TheLook Distribution (EEUU / Global)
  3. UCI Online (UK / Europa)
- **Regiones Logísticas (`dim_region`):** Se mapearán los estados de Olist, centros de distribución de TheLook y países de UCI a agrupaciones regionales.
- **Unidades de Negocio (`dim_business_unit`):** Serán mapeadas a las macro-categorías de productos de mayor jerarquía.

**Métricas:** Los reportes analíticos mostrarán las métricas reales y documentarán explícitamente cuándo una fuente no aporta datos operacionales específicos (e.g. inventario en TheLook/UCI o logística en UCI).
