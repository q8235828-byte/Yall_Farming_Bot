/**
 * Yalla Farming Studio - Cloudflare Worker License Server
 * Deploy on Cloudflare Workers (100% Free Plan).
 * Bind KV Namespace: `LICENSES_KV`
 */

const ADMIN_PASSWORD = "Admin#Secret@2026"; // Change to your desired admin secret

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

        // HWID Lock: Bind to machine on first use
        if (!license.bound_hwid) {
          license.bound_hwid = hwid;
          license.first_activated_at = new Date().toISOString();
        } else if (license.bound_hwid !== hwid) {
          return new Response(JSON.stringify({ 
            valid: false, 
            message: "HWID Mismatch! This license key is locked to another computer. Contact support to transfer." 
          }), {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" }
          });
        }

        // Update Real-Time Telemetry
        license.email = email || license.email;
        license.last_ip = client_ip;
        license.last_country = client_country;
        license.last_hostname = hostname;
        license.os_info = os_info;
        license.app_version = app_version;
        license.last_seen = new Date().toISOString();

        await env.LICENSES_KV.put(license_key, JSON.stringify(license));

        return new Response(JSON.stringify({
          valid: true,
          customer_name: license.customer_name || email || "Licensed User",
          plan: license.plan || "Enterprise Pro ($1,000)",
          expires_at: license.expires_at,
          bound_hwid: license.bound_hwid,
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

      const { customer_name, email, plan, duration_days } = await request.json();
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

    // 3. ADMIN TELEMETRY DASHBOARD
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

      const list = await env.LICENSES_KV.list();
      const records = [];
      for (const k of list.keys) {
        const val = await env.LICENSES_KV.get(k.name);
        if (val) records.push(JSON.parse(val));
      }

      const rows = records.map(r => `
        <tr style="border-bottom:1px solid #334155;">
          <td style="padding:10px;font-weight:bold;color:#38bdf8;font-family:monospace;">${r.license_key}</td>
          <td style="padding:10px;">${r.customer_name} (${r.email || '-'})</td>
          <td style="padding:10px;color:#10b981;">${r.plan}</td>
          <td style="padding:10px;font-family:monospace;color:#fbbf24;">${r.last_ip || 'Never'}</td>
          <td style="padding:10px;font-family:monospace;color:#a78bfa;">${r.bound_hwid || '<span style="color:#64748b;">Not bound</span>'}</td>
          <td style="padding:10px;"><span style="padding:3px 8px;border-radius:4px;background:#065f46;color:#34d399;font-size:11px;">${r.status}</span></td>
          <td style="padding:10px;font-size:12px;color:#94a3b8;">${r.last_seen ? new Date(r.last_seen).toLocaleString() : 'Never'}</td>
        </tr>
      `).join("");

      return new Response(`
        <!DOCTYPE html><html><head><title>Yalla Studio - Admin Licensing</title></head>
        <body style="font-family:system-ui,sans-serif;background:#090d16;color:#f8fafc;padding:2rem;">
          <div style="max-width:1100px;margin:auto;">
            <h2>🛡 Yalla Farming Bot — Admin License Telemetry</h2>
            <div style="margin:20px 0;padding:15px;background:#1e293b;border-radius:8px;">
              <strong>Active Client Licenses: ${records.length}</strong>
            </div>
            <table style="width:100%;border-collapse:collapse;background:#111827;border-radius:8px;overflow:hidden;">
              <thead style="background:#1f2937;text-align:left;">
                <tr><th style="padding:10px;">License Key</th><th style="padding:10px;">Customer</th><th style="padding:10px;">Plan</th><th style="padding:10px;">IP</th><th style="padding:10px;">Locked HWID</th><th style="padding:10px;">Status</th><th style="padding:10px;">Last Seen</th></tr>
              </thead>
              <tbody>${rows || '<tr><td colspan="7" style="padding:20px;text-align:center;color:#64748b;">No licenses generated yet.</td></tr>'}</tbody>
            </table>
          </div>
        </body></html>
      `, { headers: { "Content-Type": "text/html" } });
    }

    return new Response("Yalla Licensing Server Active", { status: 200 });
  }
};
