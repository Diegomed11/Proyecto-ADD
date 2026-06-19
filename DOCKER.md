# Ejecutar APCD con Docker

La forma más rápida de correr el proyecto: no necesitas instalar Python ni las
dependencias a mano. Solo **Docker Desktop** abierto.

## Arranque (un comando)

Usa **`-d`** (modo "detached"): la app corre en segundo plano y NO se cae si
cierras la terminal.

```bash
docker compose up -d --build   # primera vez (builda la imagen)
docker compose up -d           # siguientes veces (arranca en segundos)
```

Luego abre **http://localhost:8000**

> ⚠️ Si corres `docker compose up` **sin `-d`**, la app queda atada a esa terminal:
> al cerrarla o pulsar `Ctrl+C`, el contenedor se PARA. Por eso conviene `-d`.

Comprobar que está corriendo y parar:

```bash
docker compose ps        # debe decir "Up ... (healthy)"
docker compose stop      # parar (sin borrar)
docker compose up -d     # volver a arrancar
docker compose down      # parar y eliminar contenedores
```

## ¿Por qué es más rápido?

- **No reinstalas dependencias** cada vez: viven dentro de la imagen.
- **Los modelos de NLP se cachean** en un volumen (`hf-cache`): se descargan
  UNA sola vez y se reutilizan entre reinicios. El primer uso de cada modelo
  transformer baja sus pesos; a partir de ahí es instantáneo.
- La imagen usa **PyTorch CPU-only**, evitando ~2 GB de CUDA.

> La **primera build** sí tarda unos minutos (descarga torch + transformers).
> Es normal y solo ocurre una vez.

## Con bases de datos (PostgreSQL + MongoDB)

Las pestañas de Bases de datos y el Editor SQL necesitan una BD. Levántalas junto
con la app:

```bash
docker compose --profile databases up
```

Esto añade:
- **PostgreSQL** en `localhost:5432` — usuario `apcd`, contraseña `apcd`, base `apcd`.
- **MongoDB** en `localhost:27017`.

Desde la app, conéctate con esos datos. Como el contenedor de la app y las BD
están en la misma red de compose, dentro de la app el host de PostgreSQL es
`postgres` y el de Mongo es `mongo` (o `localhost` si conectas desde tu máquina).

## Comandos útiles

```bash
docker compose logs -f apcd     # ver logs de la app
docker compose down             # parar y quitar contenedores
docker compose down -v          # además borra los volúmenes (cache de modelos y BD)
docker compose build --no-cache # rebuild limpio
```

## Salud del contenedor

La imagen incluye un `HEALTHCHECK` contra `/health`. Comprueba el estado con:

```bash
docker ps          # columna STATUS muestra (healthy) cuando está lista
```
