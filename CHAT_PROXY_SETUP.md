# Custom chat certificate setup

By default the debugger downloads its TLS certificate from `pfx.lolcert.online` and points the Riot client at `localhost.lolcert.online`. That just works — no setup needed.

If you'd rather host your own certificate (because you don't trust the default infrastructure, want to control renewal, or are running this in a place where `lolcert.online` is blocked), follow this guide.

## What you need

- A domain you control (cheap `.xyz` from Namecheap, Porkbun, etc. — around $1-2/year).
- A free Cloudflare account.
- A place to host a small file over HTTPS. This guide uses Cloudflare R2 (free tier, no egress cost), but any static hosting works (GitHub Pages, Backblaze B2, S3, your own VPS).
- A GitHub account (for the renewal workflow).

The total setup takes about 30 minutes the first time. After that it runs itself.

## How the pieces fit together

1. A public DNS A record points `localhost.your-domain.example.com` to `127.0.0.1`. When the Riot client tries to resolve that hostname it gets `127.0.0.1`, which is your own machine.
2. A real Let's Encrypt certificate is issued for that hostname using the DNS-01 challenge (since the hostname doesn't point to a real server, HTTP-01 won't work).
3. The certificate is exported as a passwordless `.pfx` and uploaded to a public HTTPS URL.
4. The debugger downloads that `.pfx`, caches it locally, and uses it to serve TLS on its local chat proxy.
5. The Riot client connects to `localhost.your-domain.example.com:5223`, gets `127.0.0.1`, performs a TLS handshake against a valid cert, and the proxy intercepts the chat traffic.

A GitHub Actions workflow re-issues the cert monthly and re-uploads it. Let's Encrypt certs are valid for 90 days, so monthly renewal leaves plenty of margin.

## Step 1 — Buy a domain

Register any cheap domain. Skip `.xyz` if you want — `.click`, `.online`, `.site`, anything works. You won't be hosting a website on it.

## Step 2 — Move the domain to Cloudflare

1. Sign up at [cloudflare.com](https://cloudflare.com) (free).
2. Dashboard → **Add a site** → enter your domain → **Continue**.
3. Pick the **Free** plan → **Continue**.
4. Cloudflare scans existing DNS records → **Continue to activation**.
5. Cloudflare gives you two nameservers, like:
   ```
   blake.ns.cloudflare.com
   lia.ns.cloudflare.com
   ```
   Copy them.
6. Go to your registrar (Namecheap, Porkbun, etc.) → dashboard → your domain → Nameservers → switch to **Custom DNS** → paste Cloudflare's two nameservers → save.
7. Wait for Cloudflare to email you confirming the domain is active. Usually 10-30 minutes.

## Step 3 — Create the DNS record

In Cloudflare, with your domain active:

1. **DNS → Records → Add record**:

| Field | Value |
|---|---|
| Type | `A` |
| Name | `localhost` |
| IPv4 address | `127.0.0.1` |
| Proxy status | **DNS only** (gray cloud, not orange) |
| TTL | Auto |

Save. Verify from a terminal:

```
nslookup localhost.your-domain.example.com
```

Should return `127.0.0.1`. If not, wait a couple of minutes and retry.

## Step 4 — Create a Cloudflare API token

This is used by the GitHub Actions workflow to add the DNS-01 challenge record.

1. Cloudflare → top right user icon → **My Profile** → **API Tokens** → **Create Token**.
2. Use the **Edit zone DNS** template.
3. **Zone Resources**: pick your specific domain (not "all zones").
4. **Continue to summary** → **Create Token**.
5. Copy the token (only shown once).

While you're there, grab the **Zone ID** of your domain from Cloudflare → your domain dashboard → right sidebar.

## Step 5 — Set up Cloudflare R2 for hosting

This is where the `.pfx` will live.

1. Cloudflare → left sidebar → **R2 Object Storage**.
2. Accept the terms (you'll need to add a payment method, but you won't be charged within the free tier).
3. **Create bucket** → name it `cert` (or whatever) → **Create bucket**.
4. Open the bucket → **Settings** tab → **Custom Domains** → **Connect Domain**.
5. Domain: `pfx.your-domain.example.com` (any subdomain works).
6. **Continue** — Cloudflare creates the DNS record automatically. Wait a minute for it to show as **Active**.

Then create an R2 API token:

1. Sidebar → **R2 Object Storage** → **API** → **Manage API tokens** → **Create Account API token**.
2. Token name: anything (`cert-uploader`).
3. Permissions: **Object Read and Write**.
4. **Apply to specific buckets only** → select your bucket.
5. **Create**.
6. Copy the **Access Key ID**, **Secret Access Key**, and the **Account ID** (visible in the S3 API URL, e.g. `https://<account-id>.r2.cloudflarestorage.com`). Only shown once.

## Step 6 — Create the renewal workflow in GitHub

1. Create a new GitHub repository (private is fine). Add a README so it's not empty.
2. **Settings → Secrets and variables → Actions → New repository secret**. Add five secrets:

| Name | Value |
|---|---|
| `CF_API_TOKEN` | Cloudflare DNS token from step 4 |
| `CF_ZONE_ID` | Zone ID from step 4 |
| `R2_ACCESS_KEY_ID` | From step 5 |
| `R2_SECRET_ACCESS_KEY` | From step 5 |
| `R2_ACCOUNT_ID` | From step 5 |

3. Create `.github/workflows/renew.yml` in the repo:

```yaml
name: Renew certificate

on:
  schedule:
    - cron: '0 6 1 * *'
  workflow_dispatch:

jobs:
  renew:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install acme.sh
        run: curl https://get.acme.sh | sh -s email=your@email.com

      - name: Issue cert with DNS-01 via Cloudflare
        env:
          CF_Token: ${{ secrets.CF_API_TOKEN }}
          CF_Zone_ID: ${{ secrets.CF_ZONE_ID }}
        run: |
          ~/.acme.sh/acme.sh --issue \
            --dns dns_cf \
            -d "localhost.your-domain.example.com" \
            --server letsencrypt

      - name: Export as PFX (no password)
        run: |
          CERT_DIR=$(find ~/.acme.sh/ -maxdepth 1 -type d -name "localhost.your-domain.example.com*" | head -1)
          openssl pkcs12 -export \
            -in "$CERT_DIR/fullchain.cer" \
            -inkey "$CERT_DIR/localhost.your-domain.example.com.key" \
            -out localhost.pfx \
            -passout pass:

      - name: Upload PFX to R2
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: auto
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
        run: |
          aws s3 cp localhost.pfx s3://cert/localhost.pfx \
            --endpoint-url https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com \
            --content-type application/x-pkcs12
```

Replace `your@email.com`, `localhost.your-domain.example.com`, and `cert` (the bucket name) with your values. Commit.

4. Go to **Actions** → **Renew certificate** → **Run workflow** → **Run workflow**. Wait about a minute. Should turn green.

## Step 7 — Verify

```
curl -L -o test.pfx https://pfx.your-domain.example.com/localhost.pfx
openssl pkcs12 -info -noout -in test.pfx -passin pass:
```

The `openssl` call should list certificates without asking for a password. If you don't have openssl installed, just check that `test.pfx` is a few KB binary file.

## Step 8 — Point the debugger at your infrastructure

You have two ways to override the debugger's defaults. Pick whichever you prefer.

### Option A — Config file

Create a file called `chat_cert_config.json` next to `ChatCert.py` (same directory) with:

```json
{
  "pfx_url": "https://pfx.your-domain.example.com/localhost.pfx",
  "chat_proxy_host": "localhost.your-domain.example.com"
}
```

This file is in `.gitignore`, so it won't accidentally end up in version control.

### Option B — Environment variables

Set before running the debugger:

```
set LCD_PFX_URL=https://pfx.your-domain.example.com/localhost.pfx
set LCD_CHAT_PROXY_HOST=localhost.your-domain.example.com
python main.py
```

On Linux/macOS use `export` instead of `set`.

Environment variables override the JSON file if both are set.

## Step 9 — Wipe the cache and restart

The debugger caches the downloaded PFX in `~/.lcd_chat/`. After switching to your own infrastructure, clear it once so the new cert gets fetched:

```
rmdir /s /q "%USERPROFILE%\.lcd_chat"
```

(Linux/macOS: `rm -rf ~/.lcd_chat`)

Close Riot Client completely (including the tray icon), then start the debugger. Console should show:

```
[ChatCert] Downloading certificate from https://pfx.your-domain.example.com/localhost.pfx
[ChatCert] Chain with 2 certificates
[ChatCert] Certificate cached at ...
[XMPP] Proxy server started on 127.0.0.1:XXXXX (TLS)
[XMPP] League client connected to proxy (...)
[XMPP] Client connected to real riot server (...)
```

Chat should load normally in League — friends list, presence, messages, the works.

## Troubleshooting

**`HTTP 403 Forbidden` when downloading the PFX.** The CDN in front of your storage is blocking the request based on User-Agent. `ChatCert.py` already sends a real browser User-Agent so this shouldn't happen with R2 or GitHub Pages, but some providers are stricter. Try a different host.

**`WinError 64: The specified network name is no longer available`.** The TLS handshake is failing because intermediate certificates are missing. Confirm the workflow used `acme.sh`'s `fullchain.cer` (not just `<domain>.cer`) when building the PFX. The example workflow above already does this correctly.

**Chat icon stays red.** The Riot client recovered an old cached chat config. Quit the Riot Client completely (system tray → Quit), kill any leftover `RiotClient*.exe` and `LeagueClient*.exe` from Task Manager, then relaunch the client through the debugger.

**`nslookup` returns something other than `127.0.0.1`.** Your DNS hasn't propagated yet, or the registrar still points to its own nameservers. Wait. Verify the nameservers at the registrar.

**Certificate expired.** The workflow runs once a month on the 1st. If you set it up between runs, trigger it manually with **Run workflow** to get the initial cert.
