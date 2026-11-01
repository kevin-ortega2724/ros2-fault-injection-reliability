# Desviaciones respecto a PROTOCOL.md

`PROTOCOL.md` no se modifica.

## D1. La calibración de latencia se detuvo antes de acabar los estudios de señal

**Qué pasó.** El protocolo pide medir L de forma continua durante los estudios de señal. El proceso de
calibración (dominio 95) se detuvo a las 23:39-23:40 del 31-oct-2026 con `sin recuperación tras 30 s`
(`results/signal.out`), y no se reinició. Los estudios de señal acabaron a las 01:07 del 1-nov.

**Consecuencia.** L se calcula con las 2260 muestras guardadas en `results/latency.json`, tomadas durante
todo E1a, casi todo E2 y antes de E3. E3 corrió sin calibración en paralelo, así que tuvo un poco menos de
carga. No se detectó hasta analizar, por lo que la decisión de usar estas muestras no pudo influir en los datos.

**Causa probable.** No verificada. El error es compatible con un bloqueo de dominio como el del piloto.

## D2. Memoria de la máquina durante E1b

**Qué pasó.** A las 02:17 del 1-nov, durante la réplica 2, el swap de 2 GB estaba lleno y quedaban unos 1.8 GB
de RAM disponibles; un navegador abierto ocupaba más de 4 GB. Esto no se controló en el protocolo.

**Consecuencia.** No se halló ningún proceso terminado por falta de memoria en el registro del kernel, pero
no puede descartarse que la presión de memoria influya en los incidentes de E1b o en la tasa de producción.
Los incidentes se tratan como dice el protocolo.

**Incidentes.** Hubo 8 en E1b: 3 en `d_parallel`, 2 en `r2oo3` y 3 en `cen`, cada uno precedido por un `PARO`
sin recuperación durante 60 s. No se estableció la causa. Los estudios de señal no abandonaron ningún dominio.

## D3. Duración de las réplicas de E1b

El protocolo dice réplicas de 40 min y descartar los primeros 60 s. `run_cell.py` programa 41 min (40 min más 60 s).
Una corrida puede contener ocho ventanas nominales. Las ventanas van desde la primera `MARCHA` hasta el último evento
del registro; en casi todas las corridas completas sin incidente ese evento cae 2.1-6.2 s antes del final de la octava,
y quedan siete. En la réplica 1 de `d_triangle` cae 1.4 s después, y por eso tiene 22 ventanas sin incidentes. Limitar
cada corrida a siete ventanas cambia las tasas medias como máximo 0.9 cajas/h (`posthoc/results/E1b_window_variants.csv`).

## D4. Exclusión previa a un incidente

El protocolo descarta la ventana que contiene los 60 s previos al incidente. `analyze.py` descarta desde 60 s antes del
último evento registrado, unos 117 s antes de declarar el incidente. Se informa lo que hace el código congelado. Con la
redacción del protocolo, `d_parallel` gana una ventana (261.4 en vez de 262.9 cajas/h) y las demás no cambian.

## D5. Tiempo abonado tras un incidente

El protocolo no lo especifica. `run_cell.py` resta el tiempo ya transcurrido y abona una ventana más el calentamiento,
lo que alarga las corridas de las arquitecturas con incidentes.

## Análisis posteriores al congelamiento

Son exploratorios, se añadieron después de los estudios y están en `posthoc/`; no modifican los resultados
del protocolo.
- `production_sensitivity.py`: tiempo observado, usado y excluido; tasa efectiva con incidentes; réplicas; bloques.
- `model_checks.py`: forma de la reparación y umbral de detección de 0.5 s, por simulación.
- `audit_initial_state.py`: datos nuevos, n = 30 por arquitectura, semillas 7000 + índice; comprueba al inicio de cada
  intento si cada componente publica.
- `fault_anatomy.py`, `fault_frames.py`, `fault_anatomy_plot.py`: datos nuevos, ilustrativos, semillas 9000 + índice. La misma falla de enlace,
  20 veces en `d_series` (l12) y `d_parallel` (la), reparación fija de 4 s, dos celdas a la vez. Con menos carga que los estudios; no recalibra L.
- `production_heatmap.py`: tiempo detenido por minuto en E1b, solo con los registros congelados.
