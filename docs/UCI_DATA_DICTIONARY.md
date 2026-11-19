# Diccionario de Datos: UCI Online Retail

| Campo Físico | Tipo | Descripción | Tratamiento en Plataforma |
| :--- | :--- | :--- | :--- |
| `InvoiceNo` | STRING | ID de la transacción. | Mapeado a `source_order_id`. Si inicia con 'C', se tipifica como cancelación. |
| `StockCode` | STRING | ID del producto. | Mapeado a `source_product_id`. |
| `Description` | STRING | Nombre o descripción. | Mapeado a `product_name`. Usado para derivar taxonomía con REGEX. |
| `Quantity` | INT64 | Volumen transaccional. | Si >0: `items_sold`. Si <0: `return_sales` o ajuste contable. |
| `InvoiceDate` | TIMESTAMP | Fecha y hora de transacción. | Mapeado a `order_created_at`. Usado para cohortes mensuales. |
| `UnitPrice` | FLOAT64 | Precio unitario GBP. | Usado junto a Quantity para calcular `gross_sales_gbp`. |
| `CustomerID` | STRING | ID del cliente B2B/B2C. | Mapeado a `source_customer_id`. Nulos gestionados como 'ANONYMOUS'. |
| `Country` | STRING | País de facturación. | Expuesto analíticamente. Top ventas: Reino Unido. |
