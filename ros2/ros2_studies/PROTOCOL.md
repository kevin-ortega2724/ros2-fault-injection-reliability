# Estudios E1, E2 y E3: protocolo fijado antes de medir

Sigue al piloto de `../ros2_pilot/PROTOCOL.md`. Los datos de esta fase son nuevos; los del piloto solo se
usaron para planear los tamaños de muestra. Antes de congelar solo se hicieron corridas de prueba, muy
cortas y fuera de `results/`, para depurar el código; no se usan en ningún análisis.

## Común
- ROS 2 Humble, `rclpy`, DDS por defecto, solo localhost. Fuente a 20 Hz; fuente y monitor no fallan.
- SIGKILL con tiempo exponencial, media 60 s. Reinicio tras exponencial, media 4 s.
- Primer paso: desde todo operativo hasta 0.5 s sin señal en el monitor. Se exige 2 s de señal estable antes de cada intento.
- L se mide de forma continua durante los estudios de señal, en otro dominio, y se usa solo para calcular mu = 1/(4 s + L).
  Ningún parámetro se ajusta con tiempos de falla.
- IC 95 % por bootstrap con 10 000 remuestreos. Máximo seis tareas de señal a la vez.
- Fila válida: el intento empezó con señal estable. Un dominio que no recupera señal se abandona y se registra
  como incidente; no se añade fila por ello. Las filas nunca se excluyen por su duración.
- Semillas: 3000 + índice de tarea (señal), 5000 + 100·réplica + índice (celda).

## E1a. Señal, confirmatorio
Seis arquitecturas, n = 160. Predicciones: A (lógica del grafo) y B (enlaces en serie).
- C1: A es adecuada si está en el IC o a <= 15 % de la media.
- C2: B se rechaza si está fuera del IC y A no, donde A y B difieren.
- H1: `d_parallel` > `d_series`. H2: `d_triangle` > `d_series`. El IC de la diferencia debe excluir 0.

## E1b. Producción
Seis celdas Gazebo sin interfaz, una por arquitectura, una vez terminados los estudios de señal.
El controlador detiene banda y brazo con 0.5 s sin señal.
- Nominal: 10 min sin fallas. Tasa nominal R0 = cajas por hora, promedio de las seis celdas.
- Con fallas: tres réplicas de 40 min, con fallas y reinicios continuos. Se descartan los primeros 60 s y se
  divide en ventanas de 5 min. Una ventana incompleta o que contiene los 60 s previos a un incidente se descarta.
- Disponibilidad predicha: fracción estacionaria con función disponible, para A y B.
  Producción predicha: R0 × disponibilidad.
- C3: A es adecuada si su tasa está en el IC de la tasa observada (bootstrap de ventanas) o a <= 15 %.
- C4: B se rechaza si está fuera del IC y A no, donde difieren.
- Se informa además la disponibilidad observada, según los paros que registra el controlador.

## E2. Fallas de causa común
Arquitecturas `d_parallel`, `r2oo3`, `cen` y `d_units`, n = 100, beta = 0.2. Cuando vence la falla de un miembro
de un grupo redundante, con probabilidad beta caen todos los miembros operativos; si no, cae solo él.
Grupos: `la,lb`; `c1,c2,c3`; `s1,s2` y `a1,a2`; `p1,p2,p3`.
- Predicciones: A independiente, y A+CC, la misma cadena con el modelo de factor beta.
- C5: A independiente se rechaza si está fuera del IC. C6: A+CC es adecuada con el criterio de C1.
- La diferencia entre predicciones es pequeña en `d_parallel`; un resultado no concluyente allí se informa como tal.

## E3. Mensajes perdidos
Arquitecturas `d_series`, `d_parallel` y `r2oo3`, n = 60, p = 0.1, 0.2 y 0.3. Cada relé descarta cada mensaje
recibido con probabilidad p, de forma independiente. El modelo A no contiene este efecto.
- Pérdida espuria: pérdida de señal sin pérdida lógica de función. Más de 5 % significa fuera del rango del modelo.
- C7: se informa, para cada nivel, si A cumple C1 y el porcentaje de espurias.
- H3: a p = 0.3, `d_series` tiene más espurias que `d_parallel` (IC bootstrap de la diferencia excluye 0).

## Alcance
Las fallas son de software emulado y las tasas son aceleradas. La celda es simulada, con cajas y efector sin
física de contacto, y sus dimensiones son ilustrativas. No hay PLC físico ni GNN. n no se amplía según el resultado.
Cualquier cambio posterior se registra en `DEVIATIONS.md`.
