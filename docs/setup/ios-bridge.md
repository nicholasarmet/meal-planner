# iOS Bridge Setup Guide

Exposes the recipe server on your Linux machine to your iPhone via Cloudflare Tunnel.
No VPN or port forwarding required.

## What This Sets Up

- `recipe_server.py` runs on port 5050
- systemd keeps it alive across reboots
- Cloudflare Tunnel gives it a stable public URL
- An iOS Shortcut lets you save any webpage as a recipe from Safari's Share Sheet

## 1. Enable the systemd Service

```bash
sudo cp /home/nickarmet/Desktop/Projects/MealPlanner/systemd/meal-planner.service \
     /etc/systemd/system/meal-planner.service
sudo systemctl daemon-reload
sudo systemctl enable meal-planner
sudo systemctl start meal-planner
sudo systemctl status meal-planner
```

The server is now running at http://localhost:5050.

## 2. Set Your API Key

Add to `/home/nickarmet/Desktop/Projects/MealPlanner/.env`:

```
RECIPE_SERVER_API_KEY=<generate a random 32-character string>
```

Generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

Restart the service: `sudo systemctl restart meal-planner`

## 3. Install cloudflared

```bash
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```

## 4. Create a Cloudflare Tunnel

**Option A — Quick test URL (ephemeral, no account needed):**

```bash
cloudflared tunnel --url http://localhost:5050
```

Cloudflare prints a URL like `https://abc-def-ghi.trycloudflare.com`. This works
immediately but changes every time you restart cloudflared.

**Option B — Permanent URL (requires Cloudflare account + domain):**

```bash
cloudflared tunnel login
cloudflared tunnel create meal-planner
cloudflared tunnel route dns meal-planner recipes.yourdomain.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: meal-planner
credentials-file: /home/nickarmet/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: recipes.yourdomain.com
    service: http://localhost:5050
  - service: http_status:404
```

Run: `cloudflared tunnel run meal-planner`

To run as a system service: `sudo cloudflared service install`

## 5. Test the Endpoint

```bash
curl -X POST https://<your-tunnel-url>/add-recipe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{"url": "https://www.seriouseats.com/chicken-adobo-recipe"}'
```

Expected response: `{"status": "ok", "title": "Chicken Adobo", "path": "..."}`

## 6. Create the iOS Shortcut

1. Open **Shortcuts** app → tap **+** → New Shortcut
2. Tap **Add Action** → search "Receive" → choose **Receive Input from Share Sheet**
   - Set input type to: **Safari web pages**
3. Tap **+** → search "URL" → choose **URL**
   - Type: `https://<your-tunnel-url>/add-recipe`
4. Tap **+** → search "Get Contents" → choose **Get Contents of URL**
   - Method: **POST**
   - Headers: add `X-API-Key` = `<your-api-key>`
   - Request Body: **JSON**
   - Add field: key `url`, value: **Shortcut Input** (tap the variable picker)
5. Tap **+** → search "Get Dictionary" → choose **Get Dictionary Value**
   - Key: `title`  
   - Dictionary: result from previous step
6. Tap **+** → search "Notification" → choose **Show Notification**
   - Body: **Saved:** + dictionary value from step 5
7. Tap the shortcut name → rename it **"Add Recipe"**
8. Tap the share icon → enable **Show in Share Sheet**

## 7. Try It

1. Open any recipe page in Safari
2. Tap the Share button → scroll down → tap **Add Recipe**
3. The shortcut runs → notification appears → recipe is in your vault
