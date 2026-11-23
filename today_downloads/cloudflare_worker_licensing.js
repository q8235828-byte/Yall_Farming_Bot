/**
 * Cloudflare Worker: Yalla Ludo Studio License Server & Admin Telemetry
 * Deploy this on Cloudflare Workers (Free Plan).
 * Bind a KV Namespace named: `LICENSES_KV`
 */

const ADMIN_PASSWORD = "Admin#Secret@2026"; // Change to your desired admin password

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Enable CORS for client requests
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // 1. API: VERIFY LICENSE & TELEMETRY
    if (url.pathname === "/api/verify" && request.method === "POST") {
      try {
        const body = await request.json();
        const { license_key, hwid, hostname, os_info, app_version } = body;
        
        // Real-time IP detected directly from Cloudflare Edge
        const client_ip = request.headers.get("cf-connecting-ip") || body.client_ip || "Unknown";
        const client_country = request.headers.get("cf-ipcountry") || "XX";

        if (!license_key) {
          return new Response(JSON.stringify({ valid: false, message: "License key is missing." }), {
            status: 400,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // Fetch license data from KV
        const rawRecord = await env.LICENSES_KV.get(license_key);
        if (!rawRecord) {
          return new Response(JSON.stringify({ valid: false, message: "Invalid license key." }), {
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
          return new Response(JSON.stringify({ valid: false, message: "License has expired." }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // HWID Lock: Bind on first use if not already bound
        if (!license.bound_hwid) {
          license.bound_hwid = hwid;
          license.first_activated_at = new Date().toISOString();
        } else if (license.bound_hwid !== hwid) {
          return new Response(JSON.stringify({ 
            valid: false, 
            message: "HWID Mismatch! This key is locked to another computer. Contact support to transfer." 
          }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // Update Real-Time Telemetry
        license.last_ip = client_ip;
        license.last_country = client_country;
        license.last_hostname = hostname;
        license.os_info = os_info;
        license.app_version = app_version;
        license.last_seen = new Date().toISOString();

        // Save updated record back to KV
        await env.LICENSES_KV.put(license_key, JSON.stringify(license));

        return new Response(JSON.stringify({
          valid: true,
          customer_name: license.customer_name,
          plan: license.plan,
          expires_at: license.expires_at,
          bound_hwid: license.bound_hwid,
          client_ip: client_ip,
          server_time: new Date().toISOString(),
          message: "License validated successfully."
        }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ valid: false, message: err.message }), {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        });
      }
    }

    // 2. API: GENERATE NEW LICENSE (ADMIN ONLY)
    if (url.pathname === "/api/generate" && request.method === "POST") {
      const auth = request.headers.get("Authorization");
      if (auth !== `Bearer ${ADMIN_PASSWORD}`) {
        return new Response("Unauthorized", { status: 401 });
      }

      const { customer_name, plan, duration_days } = await request.json();
      const randomPart = () => Math.random().toString(36).substring(2, 6).toUpperCase();
      const key = `YALLA-${randomPart()}-${randomPart()}-${randomPart()}`;

      let expires_at = null;
      if (duration_days && duration_days > 0) {
        const d = new Date();
        d.setDate(d.getDate() + parseInt(duration_days));
        expires_at = d.toISOString();
      }

      const newRecord = {
        license_key: key,
        customer_name: customer_name || "Valued Customer",
        plan: plan || "Pro_Unlimited",
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

    // 3. ADMIN WEB DASHBOARD
    if (url.pathname === "/admin") {
      const auth = url.searchParams.get("pwd");
      if (auth !== ADMIN_PASSWORD) {
        return new Response(`
          <!DOCTYPE html><html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#fff;">
          <form method="GET" style="background:#1e293b;padding:2rem;border-radius:12px;border:1px solid #334155;text-align:center;">
            <h3>Yalla Studio Admin Login</h3>
            <input type="password" name="pwd" placeholder="Enter Admin Password" style="padding:8px 12px;border-radius:6px;border:none;margin-top:10px;width:220px;" required />
            <br/><br/>
            <button style="padding:8px 18px;background:#10b981;border:none;color:#fff;border-radius:6px;cursor:pointer;font-weight:bold;">Login</button>
          </form></body></html>
        `, { headers: { "Content-Type": "text/html" } });
      }

      // Fetch all keys from KV
      const list = await env.LICENSES_KV.list();
      const records = [];
      for (const k of list.keys) {
        const val = await env.LICENSES_KV.get(k.name);
        if (val) records.push(JSON.parse(val));
      }

      const rows = records.map(r => `
        <tr style="border-bottom:1px solid #334155;">
          <td style="padding:10px;font-weight:bold;color:#38bdf8;">${r.license_key}</td>
          <td style="padding:10px;">${r.customer_name}</td>
          <td style="padding:10px;font-family:monospace;color:#fbbf24;">${r.last_ip || 'Never connected'}</td>
          <td style="padding:10px;font-family:monospace;color:#a78bfa;">${r.bound_hwid || '<span style="color:#64748b;">Not bound yet</span>'}</td>
          <td style="padding:10px;">${r.last_hostname || '-'}</td>
          <td style="padding:10px;"><span style="padding:3px 8px;border-radius:4px;background:#065f46;color:#34d399;font-size:11px;">${r.status}</span></td>
          <td style="padding:10px;font-size:12px;color:#94a3b8;">${r.last_seen ? new Date(r.last_seen).toLocaleString() : 'Never'}</td>
        </tr>
      `).join("");

      return new Response(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Yalla Creator - Admin Telemetry Dashboard</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body style="font-family:system-ui,sans-serif;background:#090d16;color:#f8fafc;padding:2rem;">
          <div style="max-width:1100px;margin:auto;">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:1rem;margin-bottom:2rem;">
              <h2>🛡 Yalla Studio Cloud Telemetry & License Hub</h2>
              <span style="background:#1e293b;padding:6px 12px;border-radius:8px;font-size:12px;color:#10b981;border:1px solid #334155;">
                Active Clients: ${records.length}
              </span>
            </div>

            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.5rem;margin-bottom:2rem;">
              <h4 style="margin-top:0;">Generate New License Key</h4>
              <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <input id="cust" placeholder="Customer Name / Email" style="background:#0f172a;border:1px solid #334155;color:#fff;padding:8px 12px;border-radius:6px;flex:1;" />
                <select id="duration" style="background:#0f172a;border:1px solid #334155;color:#fff;padding:8px 12px;border-radius:6px;">
                  <option value="30">30 Days</option>
                  <option value="365">1 Year</option>
                  <option value="0">Lifetime</option>
                </select>
                <button onclick="createKey()" style="background:#10b981;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-weight:bold;cursor:pointer;">+ Create Key</button>
              </div>
            </div>

            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;overflow:hidden;">
              <table style="width:100%;border-collapse:collapse;text-align:left;font-size:13px;">
                <thead style="background:#0f172a;color:#94a3b8;">
                  <tr>
                    <th style="padding:12px 10px;">License Key</th>
                    <th style="padding:12px 10px;">Customer</th>
                    <th style="padding:12px 10px;">Real-Time Public IP</th>
                    <th style="padding:12px 10px;">Bound Machine HWID</th>
                    <th style="padding:12px 10px;">PC Hostname</th>
                    <th style="padding:12px 10px;">Status</th>
                    <th style="padding:12px 10px;">Last Active</th>
                  </tr>
                </thead>
                <tbody>
                  ${rows || '<tr><td colspan="7" style="padding:20px;text-align:center;color:#64748b;">No licenses created yet.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <script>
            async function createKey() {
              const cust = document.getElementById('cust').value || 'Customer';
              const days = document.getElementById('duration').value;
              const res = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': 'Bearer ${ADMIN_PASSWORD}'
                },
                body: JSON.stringify({ customer_name: cust, duration_days: parseInt(days) })
              });
              const data = await res.json();
              if (data.success) {
                alert('Created License Key: ' + data.key);
                location.reload();
              } else {
                alert('Error creating key');
              }
            }
          </script>
        </body>
        </html>
      `, { headers: { "Content-Type": "text/html" } });
    }

    return new Response("Yalla License API Operational", { status: 200 });
  }
};
