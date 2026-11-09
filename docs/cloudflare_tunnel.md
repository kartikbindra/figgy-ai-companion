# Cloudflare Tunnel Setup for Figgy Mobile Handheld Access

When your ESP32 device is away from home (connected to your mobile phone hotspot or another Wi-Fi network), it cannot directly reach your Windows PC via local IP (`192.168.x.x`). 

Instead of configuring risky router port-forwarding or setting up complex VPNs on the micro-controller, **Cloudflare Tunnel (`cloudflared`)** establishes an encrypted outbound HTTPS tunnel from your Windows PC to Cloudflare's global edge network.

---

## 1. Quick One-Line Quick Tunnel (No Account Required)

If you just want a temporary public HTTPS URL for testing:

1. Download `cloudflared` for Windows:
   ```powershell
   winget install Cloudflare.cloudflared
   ```
2. Start the Figgy backend:
   ```powershell
   .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. In a separate terminal, launch a Quick Tunnel:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
4. Cloudflare will output an HTTPS URL like:
   `https://random-subdomain.trycloudflare.com`
5. Configure your ESP32 firmware with this URL. The ESP32 can now make requests to:
   `POST https://random-subdomain.trycloudflare.com/v1/chat`

---

## 2. Permanent Named Tunnel with Custom Domain (Recommended for Friend Group)

To give Figgy a persistent hostname (e.g. `https://figgy.yourdomain.com`):

1. **Log in to Cloudflare**:
   ```powershell
   cloudflared tunnel login
   ```
2. **Create the Figgy tunnel**:
   ```powershell
   cloudflared tunnel create figgy-handheld
   ```
3. **Route DNS to your domain**:
   ```powershell
   cloudflared tunnel route dns figgy-handheld figgy.yourdomain.com
   ```
4. **Create a `config.yml` configuration**:
   ```yaml
   tunnel: <Tunnel-UUID>
   credentials-file: C:\Users\<User>\.cloudflared\<Tunnel-UUID>.json

   ingress:
     - hostname: figgy.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
5. **Run the tunnel**:
   ```powershell
   cloudflared tunnel run figgy-handheld
   ```

Now, whether you are at home, walking outside, or traveling with your phone hotspot, Figgy always connects to `https://figgy.yourdomain.com`.
