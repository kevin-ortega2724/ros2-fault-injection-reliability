# Desviaciones respecto a PROTOCOL.md

`PROTOCOL.md` no se modifica. Esta desviación se decidió antes de ejecutar `analyze.py` y sin usar los
tiempos de falla para decidir qué filas conservar.

## D1. Bloqueo del dominio DDS de `cen`

**Qué pasó.** Desde el intento 24, `cen` registró filas con `t_obs = 0`, sin pérdida lógica ni fallas
inyectadas y con `restored = False`. El reinicio completo no recuperó la señal.

**Causa probable.** Un nodo nuevo se cuelga al iniciar en el dominio 10, pero arranca en 0.2 s en los
dominios 11 y 77. `/dev/shm/fastrtps_port9917` quedó con 0 bytes desde las 16:01:12 y sin su archivo
`_el`, lo que indica una creación interrumpida. Es coherente con un SIGKILL durante el arranque de
Fast DDS. No se reprodujo el fallo de forma controlada.

**Tratamiento.**
- Copia íntegra sin modificar: `results/trials_cen_raw_incident.csv`.
- `results/trials_cen.csv` conserva las filas 0 a 23 y se excluyen las que tienen `restored = False`.
- Los intentos 24 a 59 se repiten con `resume_cen.py`: semilla 2000, dominio inicial 16.
- Ningún intento se mide sin señal restablecida; un dominio bloqueado no se reutiliza.

**Diferencias que limitan la comparación.** Los intentos nuevos corren sin las otras cinco
arquitecturas, solo con la calibración en paralelo, así que la carga de la máquina es menor. La
latencia de esta tanda se guarda aparte en `results/latency_resume.json` y la predicción sigue usando
`results/latency.json`. Se comparan ambas latencias y ambas tandas de `cen`.
