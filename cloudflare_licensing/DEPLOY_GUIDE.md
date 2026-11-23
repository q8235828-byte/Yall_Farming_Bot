# 🚀 Cloudflare Licensing & Sales Portal Deployment Guide

Deploy this system on **Cloudflare Pages & Workers** in 3 minutes (100% Free Plan).

---

## 1. Deploy the License Verification Worker (`/api/verify`)

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) and log in.
2. Navigate to **Workers & Pages -> Create Application -> Workers -> Create Worker**.
3. Name it: `yalla-licensing` (or anything you prefer).
4. Click **Deploy**.
5. Click **Edit Code**, delete existing code, and paste the contents of `cloudflare_licensing/worker.js`.
6. Click **Deploy** (top right).

### 🔑 Bind the KV Storage:
1. In Cloudflare left sidebar, click **Storage & Databases -> KV**.
2. Click **Create Namespace**, name it: `LICENSES_KV`.
3. Go back to your Worker (`yalla-licensing`) -> **Settings -> Variables & Secrets -> KV Namespace Bindings**.
4. Click **Add Binding**:
   - Variable name: `LICENSES_KV`
   - KV namespace: Select `LICENSES_KV` from dropdown.
5. Click **Save and Deploy**.

---

## 2. Deploy the Sales Website to `pages.dev`

1. Go to **Workers & Pages -> Create Application -> Pages -> Upload Assets**.
2. Project name: `yalla-farming` (Your site URL will be `https://yalla-farming.pages.dev`).
3. Upload the `cloudflare_licensing/index.html` file.
4. Click **Deploy site**.
5. Your professional sales portal is now LIVE globally!

---

## 3. How to Generate a $1,000 License Key for a Buyer

When a buyer pays $1,000 (or $150/month), you generate their key in 1 click:

### Option A: Via Admin Dashboard URL
Open your worker admin dashboard in your browser:
```text
https://yalla-licensing.your-subdomain.workers.dev/admin?pwd=Admin#Secret@2026
```
*(Shows all active clients, their locked HWID, real-time IP, country, and status).*

### Option B: Via Curl / API Command
```powershell
curl -X POST https://yalla-licensing.your-subdomain.workers.dev/api/generate `
  -H "Authorization: Bearer Admin#Secret@2026" `
  -H "Content-Type: application/json" `
  -d '{"customer_name": "Buyer Name", "email": "buyer@gmail.com", "plan": "Enterprise Lifetime ($1,000)", "duration_days": 0}'
```
*(This returns a unique key like: `YALLA-A8F2-99B1-4C3D`).*

Send this key to the buyer. When they enter it in the software on their PC, it **permanently locks to their machine HWID**. They cannot share it with anyone else!
