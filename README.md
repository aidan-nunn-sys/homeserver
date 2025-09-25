# 🏠 Aidan's HomeServer

A personal self-hosted homeserver environment powered by **Docker Compose**.  
This stack brings together essential services like Home Assistant, Plex, Pi-hole, Nginx Proxy Manager, Immich, Glance, Filebrowser, and more — all orchestrated with Docker.

---

## ✨ Features

- 🏡 **Home Assistant** — Full-featured smart home hub  
- 🎬 **Plex Media Server** — Stream your TV shows and movies  
- 🚫 **Pi-hole** — Network-wide ad-blocking and DNS filtering  
- 🌐 **Nginx Proxy Manager** — Simple reverse proxy management with SSL
- 📷 **Immich** — Self-hosted photo and video backup solution  
- 📊 **Glance** — Lightweight dashboard for your services  
- 📁 **Filebrowser** — Web file manager for your server  
- 🔄 **Watchtower** — Automatic updates for your containers  
- 🔐 **Tailscale** — Secure remote access to your network  

---

## 🚀 Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/aidan-nunn-sys/homeserver.git
cd homeserver
```

## 2. Configure environment
- Copy the example .env files where provided and update them with your secrets
- Immich requires database credentials
- Glance and other services use .env for configs
- Do not commit your .env files — keep them private

## 3. Launch Services
```bash
docker-compose up -d
```
(Or run each compose file individually depending on your setup)

## 4. Acess Services
- **Home Assistant** → ```http://<server-ip>:8123```
- **Plex** → ```http://<server-ip>:32400```
- **Pi-hole** → ```http://<server-ip>:8880```
- **Nginx Proxy Manager** → ```http://<server-ip>:81```
- **Immich** → ```http://<server-ip>:2283```
- **Glance** → ```ttp://<server-ip>:8080```
- **Filebrowser** → ```http://<server-ip>:32768```

## 🔒 Security Notes
- Replace placeholders like YOURPASSWORD and TS_AUTHKEY with your real values in local configs
- Use strong passwords and rotate them regularly

## 🛠️ Maintenance
- 🔄 Update containers automatically with **Watchtower**
- 📜 Monitor logs with:
  ```bash
  docker-compose logs -f
  ```
