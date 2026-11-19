# Calidad de Datos: UCI Online Retail

## 1. Auditoría Inicial
Durante la ingesta Bronze de UCI Online Retail, el perfilado de datos reveló:
- **Registros totales brutos:** 541,909.
- **Transacciones de venta válidas (`Quantity > 0`):** 531,285.
- **Cantidades negativas (`Quantity < 0`):** 10,624.
- **Facturas con prefijo 'C' (Cancelaciones explícitas):** 9,288.

## 2. Inconsistencias Resueltas y Gestionadas
1. **Clientes Nulos:**
   - 135,080 transacciones (24.9% del volumen bruto) no poseían `CustomerID`.
   - **Solución:** Consolidación al identificador analítico `ANONYMOUS`.
2. **Descripciones Nulas / Dispares:**
   - Identificadas 1,454 transacciones sin `Description`.
   - Elementos ruidosos o manuales (ej: "Manual", "POSTAGE", "DOTCOM POSTAGE", "AMAZON FEE").
   - **Solución:** Motor Regex para normalización en Gold que etiquetó estas transacciones bajo la categoría `Postage & Fees` o `Unclassified`.

## 3. Pruebas Automatizadas
La integración superó pruebas unitarias (`pytest backend/tests/test_uci_processing.py`) certificando:
- Las cantidades negativas son manejadas correctamente y restadas del Gross Sales.
- Las cancelaciones se etiquetan rigurosamente con los patrones esperados.
- Las agregaciones retienen exactamente el nivel esperado (541,909 filas iniciales).
