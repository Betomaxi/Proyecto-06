PROYECTO FINAL · OPCIÓN 6 de 10

Laboratorio de Técnicas de Prompting con Evaluación Cuantitativa

De «probar y ver si se ve bien» a medir con datos

Fundamentos de Arquitectura LLM · Proyecto Final

1. Contexto y motivación

La Sesión 4 presentó las técnicas de prompting (few-shot, chain-of-thought, zero-shot-CoT, role prompting) respaldadas en investigación publicada, con una precisión importante: la ganancia de chain-of-thought NO es uniforme entre tipos de tarea, según el propio paper que la introdujo (Wei et al., 2022). Esa clase de matiz —«funciona, pero no siempre, y depende de la tarea»— es exactamente el tipo de af irmación que un profesional de nivel maestría debe poder verificar por sí mismo, no solo repetir.

Este proyecto convierte al estudiante en el investigador de su propio experimento: diseñar una tarea, un dataset de prueba con respuestas correctas conocidas, y medir objetivamente qué técnica de prompting funciona mejor para ESA tarea específica —sabiendo de antemano que la respuesta puede no coincidir con la intuición inicial.

2. Objetivos de aprendizaje

Diseñar un experimento controlado: misma tarea, mismo modelo, mismos parámetros de generación, variando únicamente la técnica de prompting.

Construir un dataset de prueba propio con respuestas correctas conocidas (ground truth), condición indispensable para poder medir accuracy de forma objetiva.

Entender y comunicar la variabilidad: un LLM no da siempre la misma respuesta a la misma pregunta, por lo que una sola corrida no es evidencia suficiente.

3. Planteamiento del problema

Elegir una tarea concreta (clasificación de tickets de soporte, análisis de sentimiento, extracción de un dato numérico de un texto, resolución de un problema lógico simple, etc.), construir un dataset de al menos 20 ejemplos con la respuesta correcta conocida de antemano, y medir de forma cuantitativa el desempeño de al menos 4 técnicas de prompting distintas sobre ese mismo dataset, con múltiples corridas por técnica para capturar variabilidad.

4. Alcance funcional (qué debe hacer el sistema)

Un dataset propio de mínimo 20 ejemplos, cada uno con su respuesta correcta documentada de antemano (etiquetado manualmente por el estudiante, no generado por el mismo LLM que se va a evaluar — eso contaminaría el experimento).

Implementación de al menos 4 técnicas de prompting distintas (zero-shot, few-shot, chain-of-thought, y role prompting o zero-shot-CoT) aplicadas exactamente a la misma tarea y al mismo dataset.

Mínimo 3 corridas por técnica sobre el dataset completo, para poder reportar variabilidad (no solo un número puntual).

Cálculo de una métrica de accuracy o consistencia objetiva (comparación programática contra el ground truth, no evaluación subjetiva).

Una tabla o gráfico comparativo final con los resultados por técnica.

5. Requisitos no funcionales

El proceso de evaluación debe ser reproducible: otra persona con el mismo dataset y las mismas técnicas documentadas debería poder llegar a conclusiones similares.

Los parámetros de generación (temperature, max_tokens) deben mantenerse constantes entre técnicas para que la comparación sea justa — únicamente el prompt cambia.

6. Arquitectura sugerida

Un script o notebook que itere sobre el dataset aplicando cada técnica de prompting y registre la respuesta del modelo.

Un módulo de evaluación que compare programáticamente la respuesta del modelo contra el ground truth (exact match, o una regla de comparación adecuada a la tarea).

Un módulo de agregación de resultados que calcule accuracy promedio y variabilidad (ej. desviación estándar) por técnica a lo largo de las múltiples corridas.

7. Plan de trabajo sugerido (5 fases)

Fase 1 — Elegir la tarea y construir el dataset etiquetado manualmente, verificando que las respuestas correctas sean realmente inequívocas.

Fase 2 — Escribir los 4 prompts (uno por técnica) para la misma tarea, siguiendo las mejores prácticas de cada técnica vistas en clase.

Fase 3 — Implementar el script de evaluación automática contra el ground truth.

Fase 4 — Correr el experimento completo (todas las técnicas, múltiples corridas) y registrar los resultados crudos.

Fase 5 — Analizar los resultados y escribir una conclusión honesta —incluyendo si el resultado contradijo la intuición inicial del estudiante.

8. Entregables

El dataset completo con las respuestas correctas documentadas.

El código del experimento (prompts de cada técnica, lógica de evaluación).

Los resultados crudos de todas las corridas (no solo el promedio final) y la tabla/gráfico comparativo.

Video explicativo de máximo 30 minutos.

9. Rúbrica de evaluación (100 puntos)

Criterio	Peso	Qué se evalúa
Funcionalidad y código	30 pts	El experimento corre de punta a punta sobre el dataset completo para las 4 técnicas; la evaluación contra ground truth es programática, no manual.
Seguridad y arquitectura	20 pts	Manejo seguro de credenciales; parámetros de generación documentados y constantes entre técnicas.
Medición cuantitativa rigurosa + conclusión justificada (entregable específico)	25 pts	El dataset es válido (respuestas correctas inequívocas, no contaminadas por el propio modelo evaluado); se reporta variabilidad entre corridas, no solo un promedio; la conclusión final está respaldada por los datos obtenidos, sea cual sea el resultado.
Documentación	10 pts	La metodología del experimento está documentada con suficiente detalle para ser reproducible.
Video (máx. 30 min)	15 pts	Debe explicarse la metodología del experimento con el mismo rigor que los resultados, no solo mostrar la tabla final.
Total	100 pts	Calificación máxima del proyecto
La distribución de pesos sigue el estándar del curso: funcionalidad/código 30 pts, seguridad y arquitectura 20 pts, entregable específico del proyecto 25 pts, documentación 10 pts, video explicativo 15 pts.

10. Guía para el video (máx. 30 minutos)

El video debe responder explícitamente estas preguntas, en cualquier orden, mostrando la aplicación funcionando en vivo:

¿Qué tarea eligieron y cómo construyeron el dataset con ground truth confiable?

¿Cómo evitaron que el propio modelo evaluado contaminara la creación del dataset o del ground truth?

Muestren la tabla comparativa final: ¿qué técnica ganó y por cuánto margen, considerando la variabilidad observada?

¿El resultado coincidió con lo que esperaban antes de correr el experimento? Si no, ¿qué aprendieron de esa sorpresa?

11. Errores comunes a evitar

Usar el mismo LLM que se está evaluando para generar o validar el ground truth — esto sesga el experimento a favor del modelo.

Correr cada técnica una sola vez y reportar ese número como si fuera definitivo, ignorando que los LLMs tienen variabilidad inherente entre llamadas.

Cambiar accidentalmente los parámetros de generación entre técnicas (ej. usar temperature distinto «sin querer»), lo cual invalida la comparación.

Elegir una tarea tan simple que todas las técnicas obtienen 100% de accuracy, lo cual no permite ninguna conclusión útil — la tarea debe tener dificultad real.

12. Definición de "terminado" (checklist final)

El dataset tiene mínimo 20 ejemplos con ground truth verificado manualmente por el estudiante.

Las 4 técnicas fueron evaluadas con al menos 3 corridas cada una sobre el dataset completo.

Existe una conclusión final explícita, respaldada por los números obtenidos.

BSG · Fundamentos de Arquitectura LLM · Proyecto Final

13. Cierre y estado del proyecto (actualizado: 2026-09-30)

Estado general: la aplicación y el flujo de interfaz están implementados y verificados. El cierre académico sigue pendiente porque los resultados guardados no contienen predicciones válidas para respaldar una conclusión.

### Verificado

- [x] `Prompting-Lab/Backend/datasets/dataset.jsonl` existe y contiene 40 ejemplos: 20 en español y 20 en inglés. El conteo no sustituye la revisión humana de las etiquetas.
- [x] El backend expone los endpoints de salud, datasets y experimentos. La lista de experimentos tolera metadata legacy vacía y los archivos se descargan como Base64.
- [x] La interfaz permite configurar experimentos, revisar estados, descargar archivos, confirmar eliminación y subir datasets.
- [x] La prueba Playwright recorre la interfaz, descarga metadata, cancela la eliminación y sube/limpia un dataset temporal. Pasó en Chromium sin enviar `POST /experiments/run`.
- [x] El video de demostración técnica está en `Prompting-Lab/E2ETests/test-results/`.
- [x] La configuración local y los pasos de ejecución están en `README.md`; el contrato de endpoints está en `docs/api_contract.md`.
- [x] El servicio respondió a la interfaz y a la prueba E2E en el entorno local. Las variables de proveedor/modelo para otro entorno deben confirmarse al desplegar.

### Pendiente antes de declarar terminado

- [ ] Revisar manualmente que el ground truth de cada ejemplo sea correcto e inequívoco y que no haya sido generado por el modelo evaluado.
- [ ] Corregir y validar la ruta de inferencia/parseo de respuestas.
- [ ] Confirmar la configuración real del proveedor/modelo y los parámetros utilizados; no validar ni divulgar secretos del archivo `.env`.
- [ ] Después de corregir la inferencia, ejecutar la evaluación completa sobre los 40 ejemplos, las cuatro técnicas y al menos tres corridas por técnica. Una ejecución completa debe generar 480 registros crudos y métricas coherentes.
- [ ] Analizar accuracy y variabilidad por técnica y escribir una conclusión explícita respaldada por los resultados válidos, incluyendo si contradicen la expectativa inicial.
- [ ] Grabar el video académico de máximo 30 minutos solicitado en la rúbrica: metodología, construcción del ground truth, comparación final y aprendizaje. El video Playwright es evidencia técnica del UI y no reemplaza este entregable.
