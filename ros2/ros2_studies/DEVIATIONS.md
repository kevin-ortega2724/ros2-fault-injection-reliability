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

## Análisis posteriores al congelamiento

Son exploratorios, se añadieron después de los estudios y están en `posthoc/`; no modifican los resultados
del protocolo.
- `production_sensitivity.py`: tiempo observado, usado y excluido; tasa efectiva con incidentes; réplicas; bloques.
- `model_checks.py`: forma de la reparación y umbral de detección de 0.5 s, por simulación.
- `audit_initial_state.py`: datos nuevos, n = 30 por arquitectura, semillas 7000 + índice; comprueba al inicio de cada
  intento si cada componente publica.

**Diferencia entre código y protocolo.** Con incidente, `analyze.py` descarta desde 60 s antes del último evento
registrado, unos 117 s antes de declarar el incidente; el protocolo habla de los 60 s previos. Es algo más estricto.
Tras un incidente, `run_cell.py` abona una ventana más el calentamiento al tiempo pendiente; el protocolo no lo
detalla, y por eso hay arquitecturas con más de 21 ventanas.
