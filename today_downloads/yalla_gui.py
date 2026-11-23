import csv
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import license_client

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ACCOUNTS_CSV = os.path.join(BASE_DIR, "created_accounts.csv")


class TextRedirector:
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_val):
        try:
            self.widget.after(0, self._append, str_val)
        except Exception:
            pass

    def _append(self, str_val):
        try:
            self.widget.configure(state="normal")
            self.widget.insert("end", str_val, (self.tag,))
            self.widget.see("end")
            self.widget.configure(state="disabled")
        except Exception:
            pass

    def flush(self):
        pass


class YallaStudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yalla Ludo Automation Studio PRO v2.4")
        self.geometry("980x680")
        self.minsize(850, 600)
        self.configure(bg="#0f172a")

        self.running_thread = None
        self.is_running = False
        self.msg_queue = queue.Queue()

        # Styles
        self.setup_styles()

        # Header
        self.create_header()

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        # Create Pages
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_device = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)
        self.tab_vault = ttk.Frame(self.notebook)
        self.tab_license = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text=" ⚡ Dashboard ")
        self.notebook.add(self.tab_device, text=" 📱 Device & ADB ")
        self.notebook.add(self.tab_config, text=" ⚙ Configuration ")
        self.notebook.add(self.tab_vault, text=" 📂 Account Vault ")
        self.notebook.add(self.tab_license, text=" 🔒 License & HWID ")

        self.build_dashboard_page()
        self.build_device_page()
        self.build_config_page()
        self.build_vault_page()
        self.build_license_page()

        # Redirect standard output to Dashboard Console
        sys.stdout = TextRedirector(self.console_text, "stdout")

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e293b", foreground="#94a3b8", padding=[16, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#10b981")], foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background="#0f172a")

    def create_header(self):
        header_frame = tk.Frame(self, bg="#0f172a", height=60)
        header_frame.pack(fill="x", padx=18, pady=(12, 6))

        title_lbl = tk.Label(header_frame, text="Yalla Ludo Automation Studio", font=("Segoe UI", 16, "bold"), fg="#f8fafc", bg="#0f172a")
        title_lbl.pack(side="left")

        pro_badge = tk.Label(header_frame, text="PRO ENTERPRISE", font=("Segoe UI", 9, "bold"), fg="#10b981", bg="#064e3b", padx=6, pady=2)
        pro_badge.pack(side="left", padx=10)

        hwid = license_client.get_machine_hwid()
        hwid_lbl = tk.Label(header_frame, text=f"HWID: {hwid}", font=("Consolas", 9), fg="#94a3b8", bg="#0f172a")
        hwid_lbl.pack(side="right")

    def build_dashboard_page(self):
        p = self.tab_dashboard

        # Top Control Bar
        ctrl_frame = tk.LabelFrame(p, text=" Batch Run Controls ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=12, pady=10)
        ctrl_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(ctrl_frame, text="Batch Accounts:", fg="#f8fafc", bg="#1e293b").grid(row=0, column=0, sticky="w", padx=5)
        self.batch_count_spin = tk.Spinbox(ctrl_frame, from_=1, to=500, width=8, bg="#0f172a", fg="#10b981", font=("Segoe UI", 10, "bold"))
        self.batch_count_spin.delete(0, "end")
        self.batch_count_spin.insert(0, "5")
        self.batch_count_spin.grid(row=0, column=1, padx=5)

        self.btn_start = tk.Button(ctrl_frame, text=" ▶ START AUTOMATION ", font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#ffffff", padx=15, pady=4, relief="flat", command=self.start_batch_thread)
        self.btn_start.grid(row=0, column=2, padx=15)

        self.btn_stop = tk.Button(ctrl_frame, text=" ⏹ STOP ", font=("Segoe UI", 10, "bold"), bg="#ef4444", fg="#ffffff", padx=15, pady=4, relief="flat", command=self.stop_batch)
        self.btn_stop.grid(row=0, column=3, padx=5)

        # Progress & Status
        self.lbl_status = tk.Label(ctrl_frame, text="Status: IDLE (Ready)", font=("Segoe UI", 10, "italic"), fg="#94a3b8", bg="#1e293b")
        self.lbl_status.grid(row=0, column=4, padx=20, sticky="e")

        # Console Frame
        console_frame = tk.LabelFrame(p, text=" Real-Time Execution Log ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=8, pady=8)
        console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.console_text = tk.Text(console_frame, bg="#000000", fg="#34d399", font=("Consolas", 9), wrap="word", relief="flat")
        self.console_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(console_frame, command=self.console_text.yview)
        scroll.pack(side="right", fill="y")
        self.console_text.config(yscrollcommand=scroll.set)

    def build_device_page(self):
        p = self.tab_device
        f = tk.LabelFrame(p, text=" Connected Android Mobile Devices ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=15, pady=15)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        cols = ("Serial", "Model", "Resolution", "State", "Status")
        self.dev_tree = ttk.Treeview(f, columns=cols, show="headings", height=6)
        for c in cols:
            self.dev_tree.heading(c, text=c)
            self.dev_tree.column(c, width=130, anchor="center")
        self.dev_tree.pack(fill="x", pady=10)

        self.dev_tree.insert("", "end", values=("34558213310005P", "Vivo V2154", "1080 x 2400", "Device", "READY"))

        btn_box = tk.Frame(f, bg="#1e293b")
        btn_box.pack(fill="x", pady=10)

        tk.Button(btn_box, text="🔄 Refresh Device List", bg="#3b82f6", fg="#ffffff", relief="flat", padx=10, pady=4, command=self.refresh_devices).pack(side="left", padx=5)
        tk.Button(btn_box, text="✈ Test Airplane Mode IP Toggle", bg="#8b5cf6", fg="#ffffff", relief="flat", padx=10, pady=4, command=self.test_airplane).pack(side="left", padx=5)

    def build_config_page(self):
        p = self.tab_config
        f = tk.LabelFrame(p, text=" Catch-All Email & App Settings ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=15, pady=15)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        fields = [
            ("Cloudflare Catch-All Domain:", "cloudflare_domain"),
            ("Email Prefix:", "email_prefix"),
            ("Current Number Counter:", "current_counter"),
            ("Receiving Master Gmail:", "gmail_address"),
            ("Gmail App Password:", "gmail_app_password"),
            ("Yalla Package Name:", "yalla_package"),
            ("Airplane Wait Delay (s):", "airplane_wait_seconds")
        ]

        self.config_entries = {}
        cfg = self.load_cfg()

        for i, (label, key) in enumerate(fields):
            tk.Label(f, text=label, font=("Segoe UI", 10), fg="#f8fafc", bg="#1e293b").grid(row=i, column=0, sticky="w", pady=6)
            ent = tk.Entry(f, font=("Segoe UI", 10), width=45, bg="#0f172a", fg="#ffffff", insertbackground="#ffffff")
            ent.insert(0, str(cfg.get(key, "")))
            ent.grid(row=i, column=1, sticky="w", padx=10, pady=6)
            self.config_entries[key] = ent

        tk.Button(f, text=" 💾 Save Configuration ", font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#ffffff", relief="flat", padx=15, pady=6, command=self.save_cfg).grid(row=len(fields), column=1, sticky="e", pady=15)

    def build_vault_page(self):
        p = self.tab_vault
        f = tk.LabelFrame(p, text=" Created Accounts Vault ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=10, pady=10)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        top_b = tk.Frame(f, bg="#1e293b")
        top_b.pack(fill="x", pady=(0, 10))
        tk.Button(top_b, text="🔄 Reload CSV", bg="#3b82f6", fg="#fff", relief="flat", padx=10, pady=3, command=self.reload_csv).pack(side="left")

        cols = ("Timestamp", "Email", "Password", "OTP", "Status")
        self.vault_tree = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols:
            self.vault_tree.heading(c, text=c)
            self.vault_tree.column(c, width=140, anchor="center")
        self.vault_tree.pack(fill="both", expand=True)

        self.reload_csv()

    def build_license_page(self):
        p = self.tab_license
        f = tk.LabelFrame(p, text=" Software License & Machine Binding ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", padx=20, pady=20)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        hwid = license_client.get_machine_hwid()
        ip = license_client.get_realtime_public_ip()

        tk.Label(f, text="Your Machine HWID (Hardware ID):", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
        hwid_box = tk.Entry(f, font=("Consolas", 12, "bold"), fg="#a78bfa", bg="#0f172a", width=35, justify="center")
        hwid_box.insert(0, hwid)
        hwid_box.configure(state="readonly")
        hwid_box.pack(anchor="w", pady=(3, 15))

        tk.Label(f, text=f"Real-time Detected Public IP:  {ip}", font=("Segoe UI", 10, "bold"), fg="#34d399", bg="#1e293b").pack(anchor="w", pady=(0, 15))

        tk.Label(f, text="Enter License Key (Bought Online):", font=("Segoe UI", 10, "bold"), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
        self.key_entry = tk.Entry(f, font=("Consolas", 11), fg="#ffffff", bg="#0f172a", width=35, justify="center")
        self.key_entry.insert(0, "YALLA-PRO-2026-VIP")
        self.key_entry.pack(anchor="w", pady=(3, 15))

        tk.Button(f, text=" 🔒 Verify & Activate Online ", font=("Segoe UI", 10, "bold"), bg="#8b5cf6", fg="#ffffff", relief="flat", padx=15, pady=6, command=self.activate_key).pack(anchor="w")

    def load_cfg(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_cfg(self):
        cfg = self.load_cfg()
        for k, ent in self.config_entries.items():
            val = ent.get().strip()
            if k in ["current_counter"]:
                cfg[k] = int(val)
            elif k in ["airplane_wait_seconds"]:
                cfg[k] = float(val)
            else:
                cfg[k] = val
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        messagebox.showinfo("Saved", "Configuration updated successfully!")

    def reload_csv(self):
        for row in self.vault_tree.get_children():
            self.vault_tree.delete(row)
        if os.path.exists(ACCOUNTS_CSV):
            try:
                with open(ACCOUNTS_CSV, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None) # skip header
                    for r in reader:
                        if len(r) >= 5:
                            self.vault_tree.insert("", 0, values=(r[0], r[1], r[2], r[3], r[4]))
                        elif len(r) == 4:
                            self.vault_tree.insert("", 0, values=(r[0], r[1], "N/A", r[2], r[3]))
            except Exception:
                pass

    def refresh_devices(self):
        for r in self.dev_tree.get_children():
            self.dev_tree.delete(r)
        try:
            from airplane_mode import ADB_BIN
            out = subprocess.check_output([ADB_BIN, "devices"], text=True)
            lines = [l.strip() for l in out.strip().splitlines()[1:] if l.strip()]
            count = 0
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    ser, stat = parts[0], parts[1]
                    model = "Android Device"
                    try:
                        m = subprocess.check_output([ADB_BIN, "-s", ser, "shell", "getprop", "ro.product.model"], text=True, timeout=2).strip()
                        if m:
                            model = m
                    except Exception:
                        pass
                    res = "1080 x 2400"
                    try:
                        wm = subprocess.check_output([ADB_BIN, "-s", ser, "shell", "wm", "size"], text=True, timeout=2).strip()
                        if "Physical size:" in wm:
                            res = wm.split(":")[-1].strip()
                    except Exception:
                        pass
                    self.dev_tree.insert("", "end", values=(ser, model, res, stat, "READY"))
                    count += 1
            if count > 0:
                messagebox.showinfo("Devices", f"Refreshed: Found {count} connected ADB device(s)!")
            else:
                messagebox.showwarning("Devices", "No connected ADB devices detected. Check USB connection.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to query devices: {e}")

    def test_airplane(self):
        threading.Thread(target=lambda: os.system("python -c \"from airplane_mode import toggle_airplane_mode; toggle_airplane_mode(4.0)\""), daemon=True).start()

    def activate_key(self):
        key = self.key_entry.get().strip()
        res = license_client.verify_license_online(key)
        if res.get("valid"):
            messagebox.showinfo("License", "License Activated Successfully! HWID locked.")
        else:
            messagebox.showinfo("License", f"Status: {res.get('message', 'Validation Notice')}")

    def start_batch_thread(self):
        if self.is_running:
            return
        self.is_running = True
        self.btn_start.configure(state="disabled", bg="#64748b")
        self.lbl_status.configure(text="Status: AUTOMATION RUNNING", fg="#10b981")
        count = int(self.batch_count_spin.get())

        def run():
            try:
                import yalla_all_in_one as engine
            except Exception:
                import yalla_creator as engine
            try:
                engine.run_batch(count)
            finally:
                self.is_running = False
                self.btn_start.configure(state="normal", bg="#10b981")
                self.lbl_status.configure(text="Status: COMPLETED (Idle)", fg="#94a3b8")
                self.reload_csv()

        self.running_thread = threading.Thread(target=run, daemon=True)
        self.running_thread.start()

    def stop_batch(self):
        self.lbl_status.configure(text="Status: STOPPING...", fg="#ef4444")
        for mod in ["yalla_all_in_one", "yalla_creator"]:
            try:
                if mod in sys.modules:
                    sys.modules[mod].request_stop()
            except Exception:
                pass
        self.is_running = False


if __name__ == "__main__":
    app = YallaStudioApp()
    app.mainloop()
