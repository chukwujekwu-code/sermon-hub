# Oracle Cloud Deployment Guide

Deploy the Sermon Recommender API on Oracle Cloud's Always Free ARM instance.

## Why Oracle Cloud Free Tier

- **4 ARM Ampere A1 OCPUs + 24GB RAM** (always free, not trial)
- 200GB block storage
- 10TB/month outbound data
- More than enough for FastAPI + FastEmbed

## 1. Create Oracle Cloud Account

1. Go to [cloud.oracle.com](https://cloud.oracle.com) and sign up
2. You'll need a credit card for verification (won't be charged for free tier)
3. Choose a home region - less popular regions have better ARM availability:
   - Phoenix (US)
   - São Paulo (Brazil)
   - Sydney (Australia)
   - Mumbai (India)

## 2. Create ARM Compute Instance

1. Go to **Compute > Instances > Create Instance**

2. **Name**: `sermon-api`

3. **Image and shape**:
   - Click "Edit"
   - Image: **Ubuntu 22.04** (Canonical Ubuntu)
   - Shape: Click "Change shape"
     - Instance type: **Ampere** (ARM)
     - OCPU: **4** (max free)
     - Memory: **24 GB** (max free)

4. **Networking**:
   - Use default VCN or create new
   - Assign public IPv4 address: **Yes**

5. **Add SSH keys**:
   - Generate or upload your SSH public key
   - Save the private key if generating

6. Click **Create**

> **Note**: If ARM shape is unavailable, try:
> - Different availability domain
> - Different region
> - Try again later (instances free up)
> - Use a script to auto-retry (see Troubleshooting)

## 3. Configure Security List (Firewall)

Oracle blocks ports by default. Open HTTP/HTTPS:

1. Go to **Networking > Virtual Cloud Networks**
2. Click your VCN > **Security Lists** > Default Security List
3. **Add Ingress Rules**:

| Source CIDR | Protocol | Dest Port | Description |
|-------------|----------|-----------|-------------|
| 0.0.0.0/0   | TCP      | 80        | HTTP        |
| 0.0.0.0/0   | TCP      | 443       | HTTPS       |

## 4. Initial Server Setup

SSH into your instance:

```bash
ssh -i /path/to/private_key ubuntu@<PUBLIC_IP>
```

Update and install dependencies:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    htop \
    curl

# Also open ports in iptables (Oracle Ubuntu has this enabled)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 5. Deploy Application

### Clone and setup:

```bash
# Clone repository
cd ~
git clone https://github.com/YOUR_USERNAME/sermon_recommendation.git
cd sermon_recommendation

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Create environment file:

```bash
nano ~/.sermon_env
```

Add your environment variables:

```bash
export TURSO_DATABASE_URL="libsql://your-db.turso.io"
export TURSO_AUTH_TOKEN="your-token"
export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net"
export MONGODB_DATABASE="sermon_recommender"
export QDRANT_URL="https://your-cluster.qdrant.io"
export QDRANT_API_KEY="your-key"
export GROQ_API_KEY="your-key"
export EMBEDDING_MODEL="BAAI/bge-base-en-v1.5"
export MIN_RELEVANCE_SCORE="0.35"
```

Secure it:

```bash
chmod 600 ~/.sermon_env
```

### Test locally:

```bash
source ~/.sermon_env
cd ~/sermon_recommendation
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit `http://<PUBLIC_IP>:8000/health` - should return `{"status": "healthy"}`

Press Ctrl+C to stop.

## 6. Create Systemd Service

Create the service file:

```bash
sudo nano /etc/systemd/system/sermon.service
```

Paste:

```ini
[Unit]
Description=Sermon Recommender API
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/sermon_recommendation
EnvironmentFile=/home/ubuntu/.sermon_env
ExecStart=/home/ubuntu/sermon_recommendation/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sermon-api

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sermon
sudo systemctl start sermon
sudo systemctl status sermon
```

Check logs:

```bash
sudo journalctl -u sermon -f
```

## 7. Configure Nginx Reverse Proxy

Remove default config:

```bash
sudo rm /etc/nginx/sites-enabled/default
```

Create sermon config:

```bash
sudo nano /etc/nginx/sites-available/sermon
```

Paste (replace `your-domain.com` with your domain or use `_` for IP-only):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/sermon /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Visit `http://<PUBLIC_IP>/health`

## 8. SSL with Let's Encrypt (Optional but Recommended)

If you have a domain pointing to your server:

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will:
- Obtain certificate
- Configure nginx for HTTPS
- Set up auto-renewal

Test renewal:

```bash
sudo certbot renew --dry-run
```

## 9. Deployment Updates

Create a deploy script:

```bash
nano ~/deploy.sh
```

```bash
#!/bin/bash
set -e

cd ~/sermon_recommendation
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sermon

echo "Deployed successfully!"
```

```bash
chmod +x ~/deploy.sh
```

To deploy updates:

```bash
~/deploy.sh
```

## 10. Monitoring

### Check service status:

```bash
sudo systemctl status sermon
```

### View logs:

```bash
# Last 100 lines
sudo journalctl -u sermon -n 100

# Follow logs
sudo journalctl -u sermon -f

# Logs since today
sudo journalctl -u sermon --since today
```

### Monitor resources:

```bash
htop
```

### Check nginx access logs:

```bash
sudo tail -f /var/log/nginx/access.log
```

## Troubleshooting

### ARM instance unavailable

Create a script to auto-retry:

```bash
# install oci-cli first
# This is just an example - you'd need to configure OCI CLI
while true; do
    oci compute instance launch ... && break
    sleep 60
done
```

Or use [OCI Resource Manager](https://www.oracle.com/cloud/systems-management/resource-manager/) with Terraform.

### Service won't start

```bash
# Check logs
sudo journalctl -u sermon -n 50 --no-pager

# Test manually
source ~/.sermon_env
cd ~/sermon_recommendation
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Can't connect from internet

1. Check Oracle Security List (ingress rules for 80/443)
2. Check iptables: `sudo iptables -L -n`
3. Check nginx is running: `sudo systemctl status nginx`
4. Check sermon service: `sudo systemctl status sermon`

### Out of memory (unlikely with 24GB)

```bash
# Check memory
free -h

# If needed, add swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Update Python packages

```bash
cd ~/sermon_recommendation
source .venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart sermon
```

## Cost Summary

| Resource | Cost |
|----------|------|
| ARM Compute (4 OCPU, 24GB) | Free |
| Block Storage (50GB boot) | Free |
| Outbound Data (10TB/mo) | Free |
| Public IP | Free |
| **Total** | **$0/month** |

## Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────┐
│  Oracle Cloud (Always Free)             │
│                                         │
│  ┌─────────┐      ┌─────────────────┐  │
│  │  Nginx  │──────│  Uvicorn (x2)   │  │
│  │  :80    │      │  :8000          │  │
│  │  :443   │      │  FastAPI +      │  │
│  └─────────┘      │  FastEmbed      │  │
│                   └─────────────────┘  │
└─────────────────────────────────────────┘
    │         │           │
    ▼         ▼           ▼
 Qdrant    Turso      MongoDB
 Cloud     Cloud      Atlas
