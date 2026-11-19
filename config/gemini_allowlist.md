# Configuración Autorizada para Ejecución Autónoma (Gemini CLI)

Este documento registra los límites y operaciones permitidas para los agentes automatizados dentro de este repositorio, en respuesta al requerimiento de establecer un contexto de ejecución sin interrupciones. 

## A. Herramientas Habilitadas
La ejecución se está realizando a través de **Google Cloud Shell** con autenticación activa de Google Cloud IAM (`bchve93@gmail.com`). Las herramientas de Gemini interactúan a través de los APIs de Shell y Sistema Operativo provistos por el entorno virtual de ejecución (`run_shell_command`, `read_file`, `write_file`, `replace`).

## B. Operaciones Pre-Autorizadas
1. **Inspección y auditoría:** Consultar estado, histórico de Git, estructura de directorios y contenido de archivos sin restricciones de solo lectura.
2. **Modificación de Código:** Alteración de scripts `.py`, `.sql`, `.jsx`, `.css`, e `.html` en todo el workspace `lumina-retail`.
3. **Control de Versiones:** `git add`, `git commit` y `git push` a la rama `main` del remoto `origin`.
4. **Pruebas y Compilación:** Ejecución de suites `unittest`, `pytest`, `npm install`, `npm run build` y `gcloud builds submit`.
5. **Gobernanza WAP de BigQuery:** 
   - Autorización para consumir y actualizar tablas dentro de `lumina-retail-001.lumina_sandbox` y `lumina-retail-001.lumina_stage`.
   - Adquisición atómica de locks y ejecución de los pipelines transaccionales (`backend/app/wap_orchestrator.py`).
6. **Despliegue y Enrutamiento en Cloud Run:** 
   - Autorización para `gcloud run deploy lumina-retail --image=...`
   - Autorización para `gcloud run services update-traffic lumina-retail --to-revisions=...`

## C. Limitaciones IAM (Restricciones Irreversibles)
1. **Destrucción de Entornos:** Prohibición explícita de comandos `gcloud storage rm`, `bq rm` sobre datasets completos o históricos y `gcloud run services delete`.
2. **Modificación de IAM a nivel Proyecto/Organización:** Solo se permiten `add-iam-policy-binding` estrictamente documentados para servicio de invocación local (`roles/run.invoker`).
3. **Manejo de Credenciales:** Prohibido el commit, listado o exportación en texto plano de Service Account Keys (`.json`). El acceso debe darse exclusivamente mediante *Impersonation* o *Application Default Credentials (ADC)* proporcionados por la consola.

Esta Allowlist se hace efectiva para sesiones concurrentes asumiendo la madurez y estabilidad del branch `main` con las suites de pruebas integradas que fungen de Safety Net (Red de Seguridad).
