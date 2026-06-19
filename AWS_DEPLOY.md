# Desplegar Datia en AWS EC2

Guía paso a paso para correr la app en una instancia EC2 con Docker.
Tiempo total: ~15 min (la mayoría es esperar a que construya sola).

> **Costo:** una `t3.large` cuesta ~**$0.083/hora**. Si la enciendes solo para
> la presentación y la **apagas (Stop) o eliminas (Terminate) después**, pagas
> ~$1–2 en total. Si la dejas encendida todo el mes, ~$60.

---

## 1. Lanzar la instancia

Consola de AWS → **EC2** → **Launch instance**:

| Campo | Valor |
|---|---|
| **Name** | `datia` |
| **AMI** | Amazon Linux 2023 (x86_64) — el de por defecto |
| **Instance type** | **`t3.large`** (8 GB RAM, 2 vCPU) ⚠️ no uses micro/small |
| **Key pair** | Crea uno nuevo (`datia-key`) y descárgalo — sirve para entrar por SSH si algo falla |
| **Network → Security group** | Crea uno nuevo y permite: |
| &nbsp;&nbsp;• **HTTP** (puerto 80) | Origen **Anywhere (0.0.0.0/0)** ← para que todos vean la demo |
| &nbsp;&nbsp;• **SSH** (puerto 22) | Origen **My IP** ← solo tú, para diagnóstico |
| **Configure storage** | Cambia el volumen raíz a **30 GiB gp3** ⚠️ (los 8 por defecto NO alcanzan: imagen 2.2 GB + modelos ~3 GB) |

Despliega **Advanced details → User data** y **pega completo** el contenido de
[`deploy/ec2-userdata.sh`](deploy/ec2-userdata.sh).

Pulsa **Launch instance**.

---

## 2. Esperar a que arranque (~5–10 min)

La instancia se enciende enseguida, pero el `user data` necesita unos minutos
para instalar Docker, clonar el repo y **construir la imagen** (descarga torch +
transformers). Es normal que el primer arranque tarde.

(Opcional) Para ver el progreso, entra por SSH y mira el log:
```bash
ssh -i datia-key.pem ec2-user@<IP-pública>
sudo tail -f /var/log/cloud-init-output.log
# ...cuando veas "Datia desplegada", ya está.
sudo docker compose -f /home/ec2-user/datia/docker-compose.yml ps   # debe decir healthy
```

---

## 3. Abrir la app

En los detalles de la instancia copia **Public IPv4 address** y abre en el navegador:

```
http://<IP-pública>
```

Verás la landing de **Datia**. El botón **Empezar ahora** entra a la app.

> Es **HTTP** (no HTTPS). El navegador puede mostrar "No seguro" pero funciona
> perfectamente para una demo. (HTTPS necesitaría un dominio + certificado.)

---

## 4. Apagar para no seguir pagando

Al terminar la presentación:

- **Stop** (Instance state → Stop instance): la apagas y dejas de pagar el cómputo
  (sigues pagando ~$2/mes por el disco). Para volver: **Start**. ⚠️ La IP cambia al reiniciar.
- **Terminate** (Instance state → Terminate): la borras por completo. Ya no pagas nada.
  Para volver a usarla, repites desde el paso 1.

> Si necesitas que la IP **no cambie** entre Stop/Start, asigna una **Elastic IP**
> (EC2 → Elastic IPs → Allocate → Associate). Gratis mientras esté asociada a una
> instancia encendida.

---

## Solución de problemas

Entra por SSH (`ssh -i datia-key.pem ec2-user@<IP>`) y:

```bash
cd /home/ec2-user/datia
sudo docker compose ps                 # estado (debe ser "healthy")
sudo docker compose logs --tail 50 apcd   # logs de la app
sudo docker compose up --build -d      # reconstruir/reiniciar
curl -s localhost:80/health            # debe responder {"status":"ok"}
```

- **"no carga la página"** → revisa que el Security Group tenga el **puerto 80 abierto a 0.0.0.0/0**.
- **"se reinicia / se queda sin memoria"** → confirma que es **t3.large (8 GB)**, no una micro.
- **Actualizar el código** (tras un nuevo push):
  ```bash
  cd /home/ec2-user/datia && sudo git pull && sudo docker compose up --build -d
  ```
