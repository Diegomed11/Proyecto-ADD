#!/bin/bash
# ───────────────────────────────────────────────────────────────────────────
# Datia (APCD) — User data para EC2 (Amazon Linux 2023, x86_64).
# Pega ESTE archivo completo en "Advanced details → User data" al crear la
# instancia. Se ejecuta una sola vez, en el primer arranque, como root.
#
# Qué hace: instala Docker + compose, crea swap, clona el repo, construye y
# arranca la app. En ~5-10 min la app queda en  http://<IP-pública-de-la-instancia>
#
# Ver el progreso por SSH:  sudo tail -f /var/log/cloud-init-output.log
# ───────────────────────────────────────────────────────────────────────────
set -euxo pipefail

# 1) Docker + git
dnf update -y
dnf install -y docker git
systemctl enable --now docker

# 2) Plugin de docker compose (v2)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 3) Swap de 4 GB (red de seguridad de RAM para cuando se carga BART-large)
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# 4) Clonar el código
cd /home/ec2-user
rm -rf datia
git clone https://github.com/Diegomed11/Proyecto-ADD.git datia
cd datia

# 5) Exponer en el puerto 80 (URL limpia: http://IP, sin :8000)
cat > docker-compose.override.yml <<'YML'
services:
  apcd:
    ports:
      - "80:7860"
YML

# 6) Construir y arrancar (queda con restart unless-stopped → sobrevive reinicios)
docker compose up --build -d

echo "Datia desplegada. Abre http://<IP-pública> en unos minutos."
