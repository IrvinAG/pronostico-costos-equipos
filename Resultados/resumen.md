# Resumen de resultados

Generado por el pipeline v0.1.0 con 164 meses de datos, de 2010-01 a 2023-08.

## Qué explica el costo de cada equipo

Para cada equipo se probaron todas las combinaciones de materias primas, entrenando hasta el corte y midiendo el error en los meses posteriores. Se eligió la combinación más simple cuyo MAPE de prueba queda dentro del 10 % del mejor.

| Equipo | Variables | Coeficientes | Constante | R² | MAPE de prueba | p de cointegración | VIF máximo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equipo1 | X, Y | X: 0.198, Y: 0.800 | -0.05 | 0.9997 | 0.34 % | 0.0000 | 1.33 |
| Equipo2 | X, Y, Z | X: 0.335, Y: 0.335, Z: 0.332 | 0.64 | 0.9997 | 0.18 % | 0.0000 | 3.82 |

### Todas las combinaciones probadas

| equipo | variables | r2_entrenamiento | mape_prueba | elegida |
| --- | --- | --- | --- | --- |
| Equipo1 | X+Y+Z | 0.9997 | 0.336 | False |
| Equipo1 | X+Y | 0.9997 | 0.338 | True |
| Equipo1 | Y | 0.9979 | 0.506 | False |
| Equipo1 | Y+Z | 0.998 | 0.593 | False |
| Equipo1 | X | 0.2842 | 14.645 | False |
| Equipo1 | X+Z | 0.75 | 15.016 | False |
| Equipo1 | Z | 0.7354 | 16.26 | False |
| Equipo2 | X+Y+Z | 0.9996 | 0.179 | True |
| Equipo2 | Y+Z | 0.9966 | 0.494 | False |
| Equipo2 | X+Z | 0.9727 | 3.027 | False |
| Equipo2 | Z | 0.966 | 3.606 | False |
| Equipo2 | Y | 0.8661 | 10.509 | False |
| Equipo2 | X+Y | 0.8792 | 10.539 | False |
| Equipo2 | X | 0.3157 | 18.739 | False |

## Pronóstico de materias primas: error por horizonte

| Materia prima | Método | MAPE h=1 (%) | MAPE h=3 (%) | MAPE h=6 (%) | MAPE h=12 (%) |
| --- | --- | --- | --- | --- | --- |
| X | arima | 8.65 | 20.98 | 31.1 | 33.97 |
| X | ingenuo | 9.72 | 20.72 | 31.6 | 33.59 |
| X | suavizamiento | 10.07 | 21.27 | 32.37 | 34.51 |
| Y | arima | 5.25 | 13.47 | 20.52 | 31.61 |
| Y | ingenuo | 5.66 | 13.73 | 20.48 | 32.56 |
| Y | suavizamiento | 5.53 | 13.91 | 21.7 | 33.5 |
| Z | arima | 4.91 | 11.43 | 17.55 | 23.81 |
| Z | ingenuo | 5.17 | 11.82 | 17.67 | 23.97 |
| Z | suavizamiento | 5.22 | 12.41 | 18.33 | 26.16 |

## Pronóstico del costo de los equipos

Horizonte recomendado: **2 meses**. Es el tramo en que el intervalo del 90 % mide menos de 30 % del p50 para todos los equipos. Pasado ese punto, conviene re-pronosticar cada mes con datos nuevos.

| Equipo | Mes | p5 | p50 | p95 | Ancho (%) | Dentro del horizonte |
| --- | --- | --- | --- | --- | --- | --- |
| Equipo1 | 2023-09 | 420.49 | 459.39 | 511.5 | 19.8 | True |
| Equipo1 | 2023-10 | 405.22 | 459.51 | 538.39 | 29.0 | True |
| Equipo1 | 2023-11 | 394.74 | 459.66 | 552.13 | 34.2 | False |
| Equipo2 | 2023-09 | 860.97 | 923.24 | 992.94 | 14.3 | True |
| Equipo2 | 2023-10 | 833.47 | 926.9 | 1020.1 | 20.1 | True |
| Equipo2 | 2023-11 | 816.4 | 926.71 | 1043.05 | 24.5 | False |
