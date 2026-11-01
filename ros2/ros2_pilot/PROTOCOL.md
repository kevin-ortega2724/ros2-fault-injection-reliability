# Piloto ROS 2: protocolo fijado antes de medir

**Pregunta.** ¿Una CTMC derivada del grafo predice el tiempo hasta la pérdida de función observado en
procesos ROS 2 con fallas inyectadas? ¿La regla de enlaces en serie de `dataset_v2.0` lo predice?

**Sistema.** ROS 2 Humble, `rclpy`, DDS por defecto, solo localhost. Cada componente es un proceso; un
enlace es un proceso relé. Fuente a 20 Hz y monitor sin fallas. Arquitecturas: `configs.py`.

**Fallas.** SIGKILL con tiempos exponenciales, media 60 s. Reparación: reinicio tras exponencial de
media 4 s. Las tasas son aceleradas y las fallas son de software emuladas; no representan hardware.

**Medida.** Primer paso desde todo operativo hasta 0.5 s sin señal en el monitor. Tiempo = último
mensaje recibido menos inicio. Tras cada falla se restablece el sistema y se exige 2 s de señal estable.
n = 60 por arquitectura. Semillas 1000 + índice. Se ejecutan a la vez, en dominios DDS separados.

**Predicciones.** A: CTMC exacta con la lógica del grafo. B: la misma CTMC con todos los enlaces en
serie. Ambas con mu = 1/(4 s + L), donde L es la latencia de reinicio medida durante la misma corrida,
sola fuente de calibración. Ningún parámetro se ajusta con los tiempos de falla observados.

**Criterios.** IC 95 % bootstrap (10 000 remuestreos) de la media observada.
- C1: A es adecuada en una arquitectura si su valor está en el IC o el error relativo es <= 15 %.
- C2: B se rechaza en una arquitectura con enlaces redundantes si queda fuera del IC y A no.
- H1: la media de `d_parallel` supera a `d_series` (IC de la diferencia excluye 0), contra la regla B.
- H2: `d_triangle` supera a `d_series`, con el mismo criterio.
- Se reportan fallas espurias: pérdida de señal sin pérdida lógica de función. Más de 5 % en una
  arquitectura significa que la CTMC omite un efecto del sistema real, y se informa como hallazgo.

**Alcance.** Es un piloto: valida lógica de arquitectura en software emulado. No mide tasas reales,
no valida PLC físicos y no entrena GNN. n se fija aquí; no se amplía según el resultado.
