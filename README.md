---
title: APCD Data Pipeline
emoji: 📊
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Aplicación para Análisis de Datos en Python

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![CLI](https://img.shields.io/badge/Interface-Console-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Aplicación desarrollada en **Python** para la **carga, procesamiento, análisis y visualización de datos** utilizando una arquitectura modular basada en **Programación Orientada a Objetos (POO)**.

El sistema implementa un **pipeline de análisis de datos** que permite cargar datasets, realizar análisis exploratorio, aplicar transformaciones, entrenar modelos y evaluar resultados.

Toda la interacción con el sistema se realiza **desde consola**, permitiendo ejecutar el flujo completo de análisis de manera estructurada.

---

# Objetivo del Proyecto

El objetivo del proyecto es implementar una aplicación que modele las principales etapas de un **pipeline de análisis de datos**, utilizando una arquitectura modular y orientada a objetos.

El flujo del sistema incluye:

1. Carga de datos  
2. Análisis Exploratorio de Datos (EDA)  
3. Preprocesamiento  
4. Modelado  
5. Evaluación  
6. Visualización de resultados  

Este enfoque permite separar responsabilidades entre módulos y facilitar el mantenimiento del sistema.

---

# Tecnologías Utilizadas

| Categoría | Herramienta |
|-----------|-------------|
| Lenguaje | Python 3.11+ |
| Procesamiento de datos | Pandas |
| Cálculo numérico | NumPy |
| Machine Learning | Scikit-learn |
| Visualización | Matplotlib / Plotly |
| Control de versiones | Git + GitHub |

---

# Arquitectura del Sistema

La aplicación está organizada en **módulos especializados**, coordinados por la clase principal `Aplicacion`.

## Pipeline de análisis

```
Carga de datos
      ↓
Análisis Exploratorio (EDA)
      ↓
Preprocesamiento
      ↓
Modelado
      ↓
Evaluación
      ↓
Visualización
```

Cada componente del sistema se encarga de una etapa específica del flujo.

---

# Diagrama UML

El diseño del sistema se basa en un **diagrama UML de clases**, donde se definen las responsabilidades de cada componente y las relaciones entre ellos.

Las principales relaciones utilizadas son:

- **Composición:** la clase `Aplicacion` contiene los componentes del sistema.
- **Dependencia (usa):** algunos módulos utilizan funcionalidades de otros.

Componentes principales:

- `Aplicacion`
- `CargadorDatos`
- `AnalizadorExploratorio`
- `Preprocesador`
- `Modelador`
- `Evaluador`
- `Visualizador`

---

# Clases del Sistema

## Aplicacion

Clase principal que coordina la ejecución del pipeline de análisis.

**Atributos**

- cargador  
- analizador_eda  
- preprocesador  
- modelador  
- evaluador  
- visualizador  

**Métodos**

```
ejecutar()
inicializar_componentes()
renderizar_barra_lateral()
renderizar_metricas()
renderizar_graficas()
```

---

## CargadorDatos

Responsable de obtener los datos y almacenarlos para su procesamiento.

**Atributos**

```
url_base
tiempo_espera
datos_crudos
```

**Métodos**

```
manejar_error()
```

---

## AnalizadorExploratorio

Encargado del **Análisis Exploratorio de Datos (EDA)**.

**Atributos**

```
datos : DataFrame
```

**Métodos**

```
resumen_general()
estadisticas_descriptivas()
detectar_nulos()
detectar_atipicos(columna)
distribucion_por_categoria(columna)
```

---

## Preprocesador

Realiza la limpieza y transformación de los datos antes del modelado.

**Atributos**

```
datos
```

**Métodos**

```
filtrar_por_anio(anio)
filtrar_por_exito(exitoso)
limpiar_nulos(datos)
normalizar_fechas(datos)
a_dataframe()
obtener_anios_disponibles()
```

---

## Modelador

Encargado del análisis y generación de predicciones mediante modelos.

**Atributos**

```
datos : DataFrame
modelo
predicciones
```

**Métodos**

```
tasa_exito_por_anio()
lanzamientos_por_cohete()
analisis_tendencia()
entrenar_regresion_lineal()
predecir_proximo_anio()
obtener_coeficientes()
```

---

## Evaluador

Evalúa la calidad del modelo generado.

**Atributos**

```
valores_reales
predicciones
```

**Métodos**

```
calcular_r2()
calcular_rmse()
calcular_mae()
generar_reporte()
```

---

## Visualizador

Genera gráficos para interpretar los resultados del análisis.

**Métodos**

```
graficar_linea_temporal()
graficar_barras_comparativas()
graficar_frecuencia_mensual()
graficar_comparacion_costos()
graficar_metricas_evaluacion()
```

---

# Estructura del Proyecto

```
analisis-datos-python
│
├── src
│   ├── aplicacion.py
│   ├── cargador_datos.py
│   ├── analizador_exploratorio.py
│   ├── preprocesador.py
│   ├── modelador.py
│   ├── evaluador.py
│   └── visualizador.py
        app.pu
│
├── main.py
├── requirements.txt
    tests.txt
└── README.md
```

---

# Instalación

Clonar el repositorio:

```bash
git clone https://github.com/usuario/analisis-datos-python.git
cd analisis-datos-python
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

---

# Ejecución

Ejecutar la aplicación desde consola:

```bash
python main.py
```

El sistema ejecutará el pipeline completo de análisis de datos y mostrará los resultados.

---

# Licencia

Este proyecto se distribuye bajo la licencia **MIT**.
