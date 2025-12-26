# Mac Mini Status - speedmathsgames.com

## Current Status: ✅ RUNNING

**Public URL:** https://speedmathsgames.com/
**Local URL:** http://localhost:8001/

---

## Services Running on Mac Mini

### 1. CLAT Preparation Server
- **Status:** ✅ Running (PID: varies)
- **Port:** 8001
- **Service:** `com.clatprep.server`
- **Config:** `~/Library/LaunchAgents/com.clatprep.server.plist`
- **Logs:**
  - `/Users/arvindkumar/clat_preparation/logs/server.log`
  - `/Users/arvindkumar/clat_preparation/logs/server_error.log`

### 2. Cloudflare Tunnel
- **Status:** ✅ Running (PID: varies)
- **Service:** `com.cloudflare.tunnel`
- **Tunnel Name:** `speedmathsgames-tunnel`
- **Config:** `~/.cloudflared/config.yml`
- **Logs:**
  - `/Users/arvindkumar/clat_preparation/logs/cloudflared.log`
  - `/Users/arvindkumar/clat_preparation/logs/cloudflared_error.log`

---

## What Happens on Mac Mini Startup?

Both services **start automatically** when Mac Mini boots up because:
- `RunAtLoad: true` - Starts when user logs in
- `KeepAlive: true` - Automatically restarts if crashes

**You don't need to do anything!** The site is automatically available at https://speedmathsgames.com/

---

## Manual Service Control (If Needed)

### Check Service Status
```bash
# On Mac Mini
launchctl list | grep -i clat
launchctl list | grep -i cloudflare

# Or check remotely from MacBook Pro
ssh arvindkumar@192.168.18.4 "launchctl list | grep -E '(clat|cloudflare)'"
```

### Restart Services

**CLAT Server:**
```bash
# On Mac Mini
launchctl stop com.clatprep.server
launchctl start com.clatprep.server

# Or remotely
ssh arvindkumar@192.168.18.4 "launchctl stop com.clatprep.server && launchctl start com.clatprep.server"
```

**Cloudflare Tunnel:**
```bash
# On Mac Mini
launchctl stop com.cloudflare.tunnel
launchctl start com.cloudflare.tunnel

# Or remotely
ssh arvindkumar@192.168.18.4 "launchctl stop com.cloudflare.tunnel && launchctl start com.cloudflare.tunnel"
```

### View Logs

**Server logs:**
```bash
ssh arvindkumar@192.168.18.4 "tail -50 ~/clat_preparation/logs/server.log"
```

**Cloudflare logs:**
```bash
ssh arvindkumar@192.168.18.4 "tail -50 ~/clat_preparation/logs/cloudflared.log"
```

**Error logs:**
```bash
ssh arvindkumar@192.168.18.4 "tail -50 ~/clat_preparation/logs/server_error.log"
```

---

## Service Configuration Details

### CLAT Server (com.clatprep.server)
- **Command:** `/usr/bin/python3 /Users/arvindkumar/clat_preparation/server/unified_server.py --port 8001`
- **Working Directory:** `/Users/arvindkumar/clat_preparation`
- **Environment Variables:**
  - `ANTHROPIC_API_KEY` (set in plist)
- **Auto-restart:** Yes (KeepAlive: true)
- **Start on boot:** Yes (RunAtLoad: true)

### Cloudflare Tunnel (com.cloudflare.tunnel)
- **Command:** `/opt/homebrew/bin/cloudflared tunnel --config ~/.cloudflared/config.yml run speedmathsgames-tunnel`
- **Tunnel ID:** `7c0deb15-d51a-4f06-9251-0346e884e40a`
- **Routes:**
  - `speedmathsgames.com` → `http://localhost:8001`
  - `www.speedmathsgames.com` → `http://localhost:8001`
- **Auto-restart:** Yes (KeepAlive: true)
- **Start on boot:** Yes (RunAtLoad: true)

---

## Testing the Site

### From Mac Mini (Local)
```bash
curl http://localhost:8001/api/dashboard
```

### From MacBook Pro (Remote)
```bash
# Via local network
ssh arvindkumar@192.168.18.4 "curl -s http://localhost:8001/api/dashboard" | head -20

# Via public URL
curl https://speedmathsgames.com/api/dashboard
```

### From Browser
- https://speedmathsgames.com/
- https://speedmathsgames.com/comprehensive_dashboard.html
- https://speedmathsgames.com/assessment.html

---

## What Needs to Be Running?

For speedmathsgames.com to work, you need:

1. ✅ **Mac Mini powered on**
2. ✅ **User logged in** (for LaunchAgents to run)
3. ✅ **com.clatprep.server running** (automatic)
4. ✅ **com.cloudflare.tunnel running** (automatic)
5. ✅ **Anki running** (for assessment questions) - **MANUAL**

### Important: Anki Must Be Running

The CLAT server connects to Anki via AnkiConnect to fetch questions. Make sure:
- Anki application is running on Mac Mini
- AnkiConnect plugin is installed
- No dialog boxes blocking Anki

**To check if Anki is accessible:**
```bash
ssh arvindkumar@192.168.18.4 "curl -s -X POST http://localhost:8765 -d '{\"action\":\"version\",\"version\":6}'"
```

Should return: `{"result": 6, "error": null}`

---

## Troubleshooting

### Site Not Accessible

**1. Check Mac Mini is on:**
```bash
ping 192.168.18.4
```

**2. Check services are running:**
```bash
ssh arvindkumar@192.168.18.4 "launchctl list | grep -E '(clat|cloudflare)'"
```

**3. Check server is responding:**
```bash
ssh arvindkumar@192.168.18.4 "curl -s http://localhost:8001/api/dashboard"
```

**4. Check Cloudflare tunnel:**
```bash
ssh arvindkumar@192.168.18.4 "tail -20 ~/clat_preparation/logs/cloudflared.log"
```

**5. Test public URL:**
```bash
curl https://speedmathsgames.com/api/dashboard
```

### Server Not Starting

Check error logs:
```bash
ssh arvindkumar@192.168.18.4 "cat ~/clat_preparation/logs/server_error.log"
```

Common issues:
- Port 8001 already in use
- Missing Python dependencies
- Missing .env file (but API key is in plist)

### Assessment Questions Not Loading

This means Anki is not running or AnkiConnect is not responding:

**Solution:**
1. Start Anki on Mac Mini
2. Close any dialog boxes
3. Verify AnkiConnect is working:
   ```bash
   ssh arvindkumar@192.168.18.4 "curl -s -X POST http://localhost:8765 -d '{\"action\":\"version\",\"version\":6}'"
   ```

---

## Summary: Nothing Needs to Be Done!

**The answer to your question:**

**Nothing!**

speedmathsgames.com is **already running** and **starts automatically** when Mac Mini boots.

The only thing you may need to manually start is **Anki** (for assessment questions).

**To verify everything is working:**
```bash
# From MacBook Pro
curl https://speedmathsgames.com/api/dashboard
```

If you get a JSON response, the site is live!

---

## Architecture Flow

```
Internet User
    ↓
speedmathsgames.com (Cloudflare DNS)
    ↓
Cloudflare Tunnel (Mac Mini)
    ↓
localhost:8001 (CLAT Server)
    ↓
localhost:8765 (Anki via AnkiConnect)
```

---

## Useful Commands Reference

```bash
# Status check
ssh arvindkumar@192.168.18.4 "launchctl list | grep -E '(clat|cloudflare)'"

# Restart server after code update
ssh arvindkumar@192.168.18.4 "cd ~/clat_preparation && ./scripts/pull_from_github.sh"

# View logs
ssh arvindkumar@192.168.18.4 "tail -f ~/clat_preparation/logs/server.log"

# Test API
curl https://speedmathsgames.com/api/dashboard

# Check Anki
ssh arvindkumar@192.168.18.4 "curl -s -X POST http://localhost:8765 -d '{\"action\":\"version\",\"version\":6}'"
```
