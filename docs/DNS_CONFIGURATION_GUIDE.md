# DNS Configuration Guide

This guide explains how to configure DNS for your DigitalOcean deployment.

## Before You Start

1. You need your **DigitalOcean Droplet IP Address**
2. You need access to your **domain registrar** (GoDaddy, Namecheap, etc.)
3. Get your droplet IP: You'll see it at the end of the deployment script or check DigitalOcean dashboard

---

## Step 1: Find Your Droplet IP

After deployment, you should have an IP address like: `123.45.67.89`

If you forgot it, SSH to your droplet and run:

```bash
curl -s https://api.ipify.org
```

---

## GoDaddy DNS Configuration

### Step 1: Login to GoDaddy

1. Go to https://www.godaddy.com
2. Sign in with your account
3. Click **"My Products"** in the top menu

### Step 2: Manage DNS

1. Find your domain (e.g., `floodsense.lk`)
2. Click **"Manage"** next to the domain
3. Go to **DNS** tab

### Step 3: Add A Record for Staging Subdomain

1. Scroll to **"Records"** section
2. Click **"Add Record"** (or edit if exists)
3. Fill in:
   - **Type**: A
   - **Name**: stg
   - **Data**: YOUR_DROPLET_IP (e.g., 123.45.67.89)
   - **TTL**: 3600 (1 hour)
4. Click **"Save"**

### Step 4: Verify

```bash
# Wait 5-15 minutes
nslookup stg.floodsense.lk
# or
dig stg.floodsense.lk +short
```

---

## Namecheap DNS Configuration

### Step 1: Login to Namecheap

1. Go to https://www.namecheap.com
2. Sign in with your account
3. Go to **"Dashboard"**

### Step 2: Manage DNS

1. Click **"Domain List"**
2. Find your domain and click **"Manage"**
3. Go to **Advanced DNS** tab

### Step 3: Add A Record

1. Click **"Add New Record"**
2. Select **Type**: A Record
3. Fill in:
   - **Host**: stg
   - **Value**: YOUR_DROPLET_IP
   - **TTL**: 3600
4. Click **"Save Changes"**

### Step 4: Verify

```bash
# Wait 5-15 minutes
nslookup stg.floodsense.lk
# or
dig stg.floodsense.lk +short
```

---

## Cloudflare DNS Configuration

### Step 1: Add Domain to Cloudflare

1. Go to https://www.cloudflare.com
2. Click **"Add site"** and enter your domain
3. Select your plan (Free is fine for testing)
4. Update your domain's nameservers to Cloudflare's:
   - `iris.ns.cloudflare.com`
   - `nathan.ns.cloudflare.com`
     (Update at your current registrar)

### Step 2: Add DNS Record

1. Go to **DNS** tab in Cloudflare
2. Click **"Create record"**
3. Fill in:
   - **Type**: A
   - **Name**: stg
   - **IPv4 address**: YOUR_DROPLET_IP
   - **Proxy status**: DNS only (gray cloud) for now
   - **TTL**: Auto
4. Click **"Save"**

### Step 3: Verify

```bash
# Wait 5-30 minutes for nameserver change to propagate
nslookup stg.floodsense.lk
# or
dig stg.floodsense.lk +short
```

---

## DigitalOcean DNS (if using DigitalOcean nameservers)

### Step 1: Add Domain to DigitalOcean

1. Go to DigitalOcean Dashboard
2. Click **Networking** → **Domains**
3. Enter your domain and click **"Add Domain"**
4. Update your domain registrar's nameservers to:
   - `ns1.digitalocean.com`
   - `ns2.digitalocean.com`
   - `ns3.digitalocean.com`

### Step 2: Create A Record

1. In DigitalOcean's domain management:
2. Click **"Create Record"**
3. Select **A Record**
4. Fill in:
   - **Hostname**: stg
   - **IP**: YOUR_DROPLET_IP
   - **TTL**: 3600
5. Click **"Create Record"**

### Step 3: Verify

```bash
# Wait 5-30 minutes
nslookup stg.floodsense.lk
# or
dig stg.floodsense.lk +short
```

---

## Verify DNS is Working

### Option 1: Using nslookup (Windows/Mac/Linux)

```bash
nslookup stg.floodsense.lk
```

**Expected output:**

```
Server:     8.8.8.8
Address:    8.8.8.8#53

Non-authoritative answer:
Name:   stg.floodsense.lk
Address: 123.45.67.89
```

### Option 2: Using dig (Linux/Mac)

```bash
dig stg.floodsense.lk +short
```

**Expected output:**

```
123.45.67.89
```

### Option 3: Using host (Linux/Mac)

```bash
host stg.floodsense.lk
```

**Expected output:**

```
stg.floodsense.lk has address 123.45.67.89
```

---

## Test the Deployment

Once DNS resolves, test from your local machine:

### Test 1: Basic connectivity

```bash
curl -k https://stg.floodsense.lk/health
```

**Expected:** HTTP 200 response

### Test 2: API endpoints

```bash
curl -k https://stg.floodsense.lk/api/ping
```

**Expected:** JSON response (e.g., `{"status":"pong"}`)

### Test 3: With authentication

```bash
curl -k https://stg.floodsense.lk/api/users \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Troubleshooting DNS Issues

### Issue: DNS Not Resolving

**Symptom:** `nslookup stg.floodsense.lk` returns "cannot find"

**Solutions:**

1. Wait longer (up to 48 hours for nameserver changes)
2. Clear your DNS cache:
   - **Windows**: `ipconfig /flushdns`
   - **Mac**: `sudo dscacheutil -flushcache`
   - **Linux**: `sudo systemctl restart systemd-resolved`
3. Try a different DNS server:
   ```bash
   nslookup stg.floodsense.lk 8.8.8.8
   ```
4. Check that you added the A record (not CNAME or other type)
5. Verify the A record value matches your droplet IP exactly

### Issue: Resolves but Connection Refused

**Symptom:** `nslookup` works but `curl https://stg.floodsense.lk` fails

**Solutions:**

1. Verify services are running on droplet:
   ```bash
   docker-compose -f docker-compose.stg.yml ps
   ```
2. Check Nginx is running:
   ```bash
   systemctl status nginx
   ```
3. Check firewall rules allow port 443:
   ```bash
   sudo ufw status
   sudo ufw allow 443/tcp
   ```
4. Test locally on droplet:
   ```bash
   curl -k https://localhost/api/ping
   ```

### Issue: Certificate Warnings

**Expected behavior:** Self-signed certificate warnings (curl shows `-k` flag)

```bash
curl -k https://stg.floodsense.lk/api/ping  # -k ignores cert warnings
```

**For production:** Replace with Let's Encrypt certificate (see next section)

---

## Update to Let's Encrypt (Production)

Once DNS is working, update to free SSL certificate:

```bash
# SSH to your droplet
ssh root@YOUR_DROPLET_IP

# Install Certbot
apt-get install -y certbot python3-certbot-nginx

# Generate certificate
certbot certonly --nginx -d stg.floodsense.lk

# Update Nginx config (will be done automatically)
systemctl reload nginx

# Test without -k flag
curl https://stg.floodsense.lk/api/ping
```

Certificate will auto-renew. Check expiration:

```bash
certbot renew --dry-run
```

---

## Reference: Common DNS Records

### A Record (Points domain to IPv4)

```
Name: stg
Type: A
Value: 123.45.67.89
```

### CNAME Record (Points domain to another domain)

```
Name: stg
Type: CNAME
Value: example.com
```

### MX Record (Mail server)

```
Name: @
Type: MX
Value: mail.example.com
Priority: 10
```

---

## Summary

| Step                    | Time     | Action                                            |
| ----------------------- | -------- | ------------------------------------------------- |
| 1. Get droplet IP       | 1 min    | Run: `curl -s https://api.ipify.org`              |
| 2. Add DNS record       | 5 min    | Add A record in your registrar                    |
| 3. Wait for propagation | 5-30 min | DNS takes time to update globally                 |
| 4. Verify DNS           | 2 min    | Run: `nslookup stg.floodsense.lk`                 |
| 5. Test endpoint        | 2 min    | Run: `curl -k https://stg.floodsense.lk/api/ping` |

**Total time: ~30-45 minutes**

---

## Still Having Issues?

1. Check Kong logs on droplet:

   ```bash
   docker-compose -f docker-compose.stg.yml logs kong | tail -50
   ```

2. Check Nginx logs:

   ```bash
   tail -50 /var/log/nginx/error.log
   ```

3. Verify Kong Konnect connection:

   ```bash
   source .env
   curl -X GET "${KONNECT_ADDR}/v2/control-planes" \
     --header "Authorization: Bearer ${KONNECT_TOKEN}" | jq .
   ```

4. See detailed troubleshooting in: [DROPLET_DEPLOYMENT_STEPS.md](DROPLET_DEPLOYMENT_STEPS.md)
