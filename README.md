🏠 Aidan's HomeServer

A personal self-hosted homeserver environment powered by Docker Compose. This stack brings together essential services like Home Assistant, Plex, Pi-hole, Nginx Proxy Manager, Immich, Glance, Filebrowser, and more — all orchestrated with Docker.

✨ Features

•	Home Assistant — Full-featured smart home hub.

•	Plex Media Server — Stream your TV shows and movies.

•	Pi-hole — Network-wide ad-blocking and DNS filtering.

•	Nginx Proxy Manager — Simple reverse proxy management with SSL.

•	Immich — Self-hosted photo and video backup solution.

•	Glance — Lightweight dashboard for your services.

•	Filebrowser — Web file manager for your server.

•	Watchtower — Automatic updates for your containers.

•	Tailscale — Secure remote access to your network.

🚀 Getting Started
1. Clone the repo

<pre>
	git clone https://github.com/(your-username)/(your-repo).git
	cd (your-repo)
</pre>

2. Configure environment
   
	•	Copy the example .env files where provided and update them with your secrets:

	•	IMMICH requires database credentials.

	•	Glance and others use .env for configs.

	•	Do not commit your .env files — keep them private.

4. Launch services
<pre>
	docker-compose up -d
</pre>

(Or run each compose file individually depending on your setup.)

4. Access services

	•	Home Assistant → http://<server-ip>:8123

	•	Plex → http://<server-ip>:32400

	•	Pi-hole → http://<server-ip>:8880

	•	Nginx Proxy Manager → http://<server-ip>:81

	•	Immich → http://<server-ip>:2283

	•	Glance → http://<server-ip>:8080

	•	Filebrowser → http://<server-ip>:32768

🔒 Security Notes

•	Replace placeholders like YOURPASSWORD and TS_AUTHKEY with your real values in local configs.

•	Never commit your .env files, auth keys, claim tokens, or database files.

•	Use strong passwords and rotate them regularly.

🛠️ Maintenance

•	Update containers automatically with Watchtower.

•	Backup configs and volumes (see ./config, ./etc-pihole, etc.).

•	Monitor logs with:
