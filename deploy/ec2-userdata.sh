#!/bin/bash
# ───────────────────────────────────────────────────────────────────────────
# Datia (APCD) — User data para EC2 con UBUNTU (Ubuntu Server, x86_64).
# Pega ESTE archivo completo en "Detalles avanzados → Datos de usuario" al
# crear la instancia. Se ejecuta una sola vez, en el primer arranque, como root.
#
# Qué hace: instala Docker + compose, crea swap, clona el repo, construye y
# arranca la app. En ~5-10 min la app queda en  http://<IP-pública-de-la-instancia>
#
# Ver el progreso por SSH:  sudo tail -f /var/log/cloud-init-output.log
# ───────────────────────────────────────────────────────────────────────────
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

# 1) Docker + plugin compose (paquetes de Ubuntu) + git
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git curl
systemctl enable --now docker

# 2) Swap de 4 GB (red de seguridad de RAM para cuando se carga BART-large)
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# 3) Clonar el código (en el home del usuario 'ubuntu')
cd /home/ubuntu
rm -rf datia
git clone https://github.com/Diegomed11/Proyecto-ADD.git datia
cd datia

# 4) Exponer en el puerto 80 (URL limpia: http://IP, sin :8000)
cat > docker-compose.override.yml <<'YML'
services:
  apcd:
    ports:
      - "80:7860"
YML

# 5) Construir y arrancar (restart unless-stopped → sobrevive reinicios)
docker compose up --build -d

echo "Datia desplegada. Abre http://<IP-pública> en unos minutos."
