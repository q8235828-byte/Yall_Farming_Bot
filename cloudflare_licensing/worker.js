/**
 * Yalla Farming Studio - Cloudflare Worker License Server v2.0
 * Deploy on Cloudflare Workers (100% Free Plan).
 * Bind KV Namespace: `LICENSES_KV`
 */

const VALID_PASSWORDS = ["AdminSecret2026", "Admin#Secret@2026", "admin123", "Admin@2026"];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // 1. API: VERIFY LICENSE & HWID LOCK
    if (url.pathname === "/api/verify" && request.method === "POST") {
      try {
        const body = await request.json();
        const { license_key, email, hwid, hostname, os_info, app_version } = body;
        
        const client_ip = request.headers.get("cf-connecting-ip") || "Unknown";
        const client_country = request.headers.get("cf-ipcountry") || "XX";

        if (!license_key) {
          return new Response(JSON.stringify({ valid: false, message: "License key is missing." }), {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // Fetch license data from Cloudflare KV
        const rawRecord = await env.LICENSES_KV.get(license_key);
        if (!rawRecord) {
          return new Response(JSON.stringify({ valid: false, message: "Invalid license key. Please purchase from https://yalla-farming.pages.dev" }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        const license = JSON.parse(rawRecord);

        // Check if Revoked or Expired
        if (license.status !== "active") {
          return new Response(JSON.stringify({ valid: false, message: `License is ${license.status}.` }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        if (license.expires_at && new Date(license.expires_at) < new Date()) {
          return new Response(JSON.stringify({ valid: false, message: "License has expired. Please renew your subscription." }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // HWID Binding Logic (1 PC per License)
        if (!license.bound_hwid) {
          license.bound_hwid = hwid;
          license.first_activated_at = new Date().toISOString();
        } else if (license.bound_hwid !== hwid) {
          return new Response(JSON.stringify({
            valid: false,
            message: `HWID mismatch! This license is already bound to hardware ID: ${license.bound_hwid}. Contact support to reset.`
          }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // Update telemetry
        license.last_seen = new Date().toISOString();
        license.last_ip = client_ip;
        license.last_country = client_country;
        if (hostname) license.last_hostname = hostname;
        if (os_info) license.os_info = os_info;
        if (app_version) license.app_version = app_version;

        await env.LICENSES_KV.put(license_key, JSON.stringify(license));

        return new Response(JSON.stringify({
          valid: true,
          plan: license.plan,
          customer_name: license.customer_name,
          bound_hwid: license.bound_hwid,
          expires_at: license.expires_at,
          status: license.status
        }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });

      } catch (err) {
        return new Response(JSON.stringify({ valid: false, error: err.message }), {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      }
    }

    // 2. API: GENERATE NEW LICENSE (Admin API)
    if (url.pathname === "/api/generate" && request.method === "POST") {
      const auth = request.headers.get("Authorization") || url.searchParams.get("pwd") || "";
      const pwd = auth.replace("Bearer ", "").trim();
      if (!VALID_PASSWORDS.includes(pwd)) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers: corsHeaders });
      }

      const body = await request.json();
      const { customer_name, email, plan, duration_days } = body;

      // Generate Random License Key: YALLA-XXXX-XXXX-XXXX
      const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
      const part = () => Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
      const key = `YALLA-${part()}-${part()}-${part()}`;

      let expires_at = null;
      if (duration_days && duration_days > 0) {
        const d = new Date();
        d.setDate(d.getDate() + parseInt(duration_days));
        expires_at = d.toISOString();
      }

      const newRecord = {
        license_key: key,
        customer_name: customer_name || "Valued Client",
        email: email || "",
        plan: plan || "Enterprise Lifetime Pro ($1,000)",
        created_at: new Date().toISOString(),
        expires_at: expires_at,
        status: "active",
        bound_hwid: null,
        last_ip: null,
        last_hostname: null,
        last_seen: null
      };

      await env.LICENSES_KV.put(key, JSON.stringify(newRecord));
      return new Response(JSON.stringify({ success: true, key: key, record: newRecord }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }

    // 3. API: REVOKE / DELETE LICENSE
    if (url.pathname === "/api/delete" && request.method === "POST") {
      const auth = request.headers.get("Authorization") || url.searchParams.get("pwd") || "";
      const pwd = auth.replace("Bearer ", "").trim();
      if (!VALID_PASSWORDS.includes(pwd)) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers: corsHeaders });
      }

      const body = await request.json();
      const { license_key } = body;
      if (license_key) {
        await env.LICENSES_KV.delete(license_key);
        return new Response(JSON.stringify({ success: true, deleted: license_key }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ error: "No key provided" }), { status: 400, headers: corsHeaders });
    }

    // 4. ADMIN TELEMETRY DASHBOARD
    if (url.pathname === "/admin") {
      const auth = url.searchParams.get("pwd") || "";
      if (!VALID_PASSWORDS.includes(auth)) {
        return new Response(`
          <!DOCTYPE html><html><head><title>Admin Login - Yalla Licensing</title>
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <script src="https://cdn.tailwindcss.com"></script></head>
          <body class="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
            <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl text-center space-y-6">
              <div class="w-16 h-16 bg-emerald-500/10 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto text-3xl font-bold border border-emerald-500/20">
                🛡️
              </div>
              <div>
                <h2 class="text-xl font-bold tracking-tight">Yalla Studio License Admin</h2>
                <p class="text-xs text-slate-400 mt-1">Enter your admin password to manage client licenses</p>
              </div>
              <form method="GET" class="space-y-4">
                <input type="password" name="pwd" placeholder="Enter Admin Password (e.g. AdminSecret2026)" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-emerald-500" required autofocus />
                <button type="submit" class="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold rounded-xl text-sm transition">
                  Unlock Admin Dashboard
                </button>
              </form>
            </div>
          </body></html>
        `, { headers: { "Content-Type": "text/html" } });
      }

      const list = await env.LICENSES_KV.list();
      const records = [];
      for (const k of list.keys) {
        const val = await env.LICENSES_KV.get(k.name);
        if (val) records.push(JSON.parse(val));
      }

      const rows = records.map(r => `
        <tr class="hover:bg-slate-800/40 border-b border-slate-800 transition">
          <td class="py-3 px-4 font-mono font-bold text-sky-400 select-all">${r.license_key}</td>
          <td class="py-3 px-4">${r.customer_name} <br/><span class="text-slate-400 text-xs">${r.email || '-'}</span></td>
          <td class="py-3 px-4 text-emerald-400 font-medium">${r.plan}</td>
          <td class="py-3 px-4 font-mono text-xs text-amber-300">${r.last_ip || 'Never'}</td>
          <td class="py-3 px-4 font-mono text-xs text-purple-300">${r.bound_hwid || '<span class="text-slate-500 italic">Not bound yet</span>'}</td>
          <td class="py-3 px-4"><span class="px-2.5 py-0.5 rounded-full text-xs font-semibold ${r.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400'}">${r.status}</span></td>
          <td class="py-3 px-4 text-xs text-slate-400">${r.last_seen ? new Date(r.last_seen).toLocaleString() : 'Never'}</td>
          <td class="py-3 px-4">
            <button onclick="deleteKey('${r.license_key}')" class="px-2 py-1 text-xs bg-rose-900/40 hover:bg-rose-600 text-rose-300 hover:text-white rounded border border-rose-800 transition">Delete</button>
          </td>
        </tr>
      `).join("");

      return new Response(`
        <!DOCTYPE html><html><head><title>Yalla Studio — Admin Licensing</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="min-h-screen bg-slate-950 text-slate-100 p-6">
          <div class="max-w-6xl mx-auto space-y-6">
            
            <!-- Header -->
            <div class="flex flex-col md:flex-row items-center justify-between border-b border-slate-800 pb-4 gap-4">
              <div>
                <h1 class="text-2xl font-bold flex items-center gap-2">🛡️ Yalla Studio — Enterprise Licensing Control</h1>
                <p class="text-xs text-slate-400">Generate, lock HWID, and monitor client bots across the globe</p>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">Cloudflare KV Online</span>
                <a href="/admin" class="px-3 py-1 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs">Logout</a>
              </div>
            </div>

            <!-- Generate Key Card -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <h2 class="text-sm font-bold text-emerald-400 uppercase tracking-wider">⚡ 1-Click License Generator</h2>
              <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label class="text-xs text-slate-400 block mb-1">Customer Name</label>
                  <input type="text" id="genName" placeholder="e.g. John Doe" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white" />
                </div>
                <div>
                  <label class="text-xs text-slate-400 block mb-1">Customer Email</label>
                  <input type="email" id="genEmail" placeholder="client@example.com" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white" />
                </div>
                <div>
                  <label class="text-xs text-slate-400 block mb-1">License Plan</label>
                  <select id="genPlan" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white">
                    <option value="Enterprise Lifetime Pro ($1,000)">Enterprise Lifetime Pro ($1,000)</option>
                    <option value="Monthly Pro ($150/mo)">Monthly Pro ($150/mo)</option>
                    <option value="7-Day Trial">7-Day Trial</option>
                  </select>
                </div>
                <div class="flex items-end">
                  <button onclick="generateKey()" class="w-full py-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-slate-950 font-bold rounded-xl text-xs transition shadow-lg shadow-emerald-500/20">
                    + GENERATE NEW KEY
                  </button>
                </div>
              </div>

              <div id="genResultBox" class="hidden p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs flex items-center justify-between">
                <span>New License Key Generated: <strong id="genKeyText" class="text-white font-mono text-sm select-all"></strong></span>
                <button onclick="copyGeneratedKey()" class="px-3 py-1 bg-emerald-500 text-slate-950 font-bold rounded-lg text-xs">Copy Key</button>
              </div>
            </div>

            <!-- Licenses Table -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
              <div class="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 class="text-sm font-bold text-white">Active Client Licenses (${records.length})</h3>
                <span class="text-xs text-slate-500">Auto-synced with Cloudflare KV</span>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-xs">
                  <thead class="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th class="py-3 px-4">License Key</th>
                      <th class="py-3 px-4">Customer</th>
                      <th class="py-3 px-4">Plan</th>
                      <th class="py-3 px-4">Last IP</th>
                      <th class="py-3 px-4">Bound HWID</th>
                      <th class="py-3 px-4">Status</th>
                      <th class="py-3 px-4">Last Seen</th>
                      <th class="py-3 px-4">Action</th>
                    </tr>
                  </thead>
                  <tbody>${rows || '<tr><td colspan="8" class="text-center py-8 text-slate-500">No active licenses found.</td></tr>'}</tbody>
                </table>
              </div>
            </div>

          </div>

          <script>
            const PWD = "${auth}";
            async function generateKey() {
              const name = document.getElementById('genName').value.trim();
              const email = document.getElementById('genEmail').value.trim();
              const plan = document.getElementById('genPlan').value;
              const days = plan.includes('Monthly') ? 30 : (plan.includes('Trial') ? 7 : 0);

              const res = await fetch('/api/generate?pwd=' + encodeURIComponent(PWD), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ customer_name: name, email: email, plan: plan, duration_days: days })
              });
              const data = await res.json();
              if (data.success) {
                document.getElementById('genKeyText').innerText = data.key;
                document.getElementById('genResultBox').classList.remove('hidden');
                setTimeout(() => window.location.reload(), 3000);
              } else {
                alert('Error: ' + data.error);
              }
            }

            function copyGeneratedKey() {
              const k = document.getElementById('genKeyText').innerText;
              navigator.clipboard.writeText(k);
              alert('Copied License Key: ' + k);
            }

            async function deleteKey(k) {
              if (!confirm('Are you sure you want to revoke/delete license: ' + k + '?')) return;
              const res = await fetch('/api/delete?pwd=' + encodeURIComponent(PWD), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ license_key: k })
              });
              const data = await res.json();
              if (data.success) {
                alert('License deleted successfully!');
                window.location.reload();
              } else {
                alert('Failed to delete: ' + data.error);
              }
            }
          </script>
        </body></html>
      `, { headers: { "Content-Type": "text/html" } });
    }

    return new Response("Yalla Licensing Server Active", { status: 200 });
  }
};
