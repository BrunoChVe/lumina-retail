# UCI Online Retail - Evaluación de Experimento Predictivo

## 1. Contexto

Se solicitó evaluar un experimento independiente de forecasting de demanda (Machine Learning o estadístico) utilizando el dataset de **UCI Online Retail**. El objetivo era predecir la demanda semanal por producto o categoría, comparando modelos baseline como Naive y Seasonal Naive.

## 2. Análisis de Viabilidad

Al auditar la cobertura temporal de los datos de UCI Online Retail en `lumina-retail-001.lumina_stage.stg_uci_online_retail`, se obtuvieron los siguientes resultados:

- **Fecha mínima:** 2010-12-01
- **Fecha máxima:** 2011-12-09
- **Semanas observadas:** 53 semanas (apenas 1 año).

## 3. Motivo de Inviabilidad

El experimento de forecasting para la fuente UCI se declara **metodológicamente inviable** por las siguientes razones:

1. **Ausencia de profundidad histórica para estacionalidad (t-52):** Un modelo de forecasting en retail, como el `Seasonal Naive` implementado en Olist, requiere como mínimo dos años de historia completa: un año para capturar el patrón anual (training) y el subsecuente para la evaluación (testing). Con 53 semanas en total, es imposible calcular el `lag_52` y tener un conjunto de test representativo sin generar data leakage o truncar masivamente el dataset.
2. **Imposibilidad de validación cruzada temporal robusta:** Dividir 53 semanas en conjuntos de entrenamiento y prueba dejaría un tamaño de muestra insuficiente para un modelo de Machine Learning (ej. LightGBM), provocando sobreajuste (overfitting) o resultados espurios.
3. **Restricción de mezcla de fuentes:** Siguiendo las directrices del proyecto ("No mezcles UCI, Olist y TheLook en un mismo modelo sin justificación metodológica"), la falta de variables compartidas como geografía de alta resolución y taxonomías logísticas hacen que sea incorrecto unir la historia británica de 2010/2011 con el eCommerce de Brasil de 2017/2018 para aumentar las observaciones.

## 4. Conclusión y Siguiente Acción

En consecuencia, el módulo `Predictive` mantendrá el modelo de demanda validado sobre Olist, mientras que la demanda de UCI se explotará de manera puramente descriptiva en los módulos de `Overview` y `Commercial`. No se publicarán métricas sintéticas de Machine Learning para UCI a fin de preservar la integridad estadística del proyecto LUMINA Retail.
