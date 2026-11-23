"""
================================================================================
GITHUB LIVE ROTATING PROXY MANAGER (HIGH SPEED 2-STAGE VALIDATION)
================================================================================
Fetches live, real-time public proxy lists directly from top maintained GitHub
repositories, concurrently validates latency using Google CDN generate_204,
and rotates IPs on MEmu Android instances via ADB.

Sources:
1. monosans/proxy-list (Updated every 30 mins)
2. TheSpeedX/PROXY-List (Massive verified pool)
3. roosterkid/openproxylist (Fast HTTPS proxies)
================================================================================
"""

import concurrent.futures
import json
import logging
import os
import random
import socket
import subprocess
import threading
import time
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [ProxyRotator] %(message)s")
logger = logging.getLogger("ProxyRotator")

GITHUB_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
]

# Standard Android Connectivity Check Target (Google CDN - Zero rate-limiting, <100ms)
FAST_TARGET = "http://connectivitycheck.gstatic.com/generate_204"


class GitHubProxyRotator:
    def __init__(self, min_pool_size: int = 15, tcp_timeout: float = 0.5, http_timeout: float = 1.2):
        self.min_pool_size = min_pool_size
        self.tcp_timeout = tcp_timeout
        self.http_timeout = http_timeout
        self.raw_proxies = []
        self.working_pool = []
        self.used_proxies = set()
        self.lock = threading.Lock()
        self.is_refreshing = False
        self.device_current_proxy = {}

    def fetch_github_lists(self) -> list[str]:
        """Downloads proxy lists from GitHub raw URLs."""
        all_proxies = set()
        for url in GITHUB_PROXY_SOURCES:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                    count = 0
                    for line in lines:
                        p = line.strip()
                        if p and ":" in p and not p.startswith("#"):
                            all_proxies.add(p)
                            count += 1
                    logger.info(f"Loaded {count} proxies from GitHub: {url.split('/')[4]}")
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")

        self.raw_proxies = list(all_proxies)
        random.shuffle(self.raw_proxies)
        logger.info(f"Total raw proxies loaded: {len(self.raw_proxies)}")
        return self.raw_proxies

    def _fast_tcp_check(self, ip: str, port: int) -> bool:
        """Stage 1: Ultra-fast socket handshake (<0.5s)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.tcp_timeout)
            res = s.connect_ex((ip, port))
            s.close()
            return res == 0
        except Exception:
            return False

    def _http_confirm(self, proxy: str) -> bool:
        """Stage 2: Google CDN HTTP 204 ping."""
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": f"http://{proxy}"})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(FAST_TARGET, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=self.http_timeout) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def validate_proxy(self, proxy: str) -> str | None:
        try:
            parts = proxy.split(":")
            ip = parts[0]
            port = int(parts[1])
            if not self._fast_tcp_check(ip, port):
                return None
            if self._http_confirm(proxy):
                return proxy
        except Exception:
            pass
        return None

    def refresh_working_pool(self, target_count: int = 15):
        """Scans raw proxies with multi-threading to find verified live proxies."""
        with self.lock:
            if self.is_refreshing:
                return
            self.is_refreshing = True

        try:
            if not self.raw_proxies:
                self.fetch_github_lists()

            logger.info(f"Verifying live proxies (target: {target_count})...")
            batch_size = min(300, len(self.raw_proxies))
            test_batch = random.sample(self.raw_proxies, batch_size)

            new_working = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
                futures = {executor.submit(self.validate_proxy, p): p for p in test_batch}
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res and res not in self.working_pool and res not in new_working:
                        new_working.append(res)
                        logger.info(f"[+] Verified Fast Proxy: {res} ({len(new_working)}/{target_count})")
                        if len(new_working) >= target_count:
                            for f in futures:
                                f.cancel()
                            break

            with self.lock:
                self.working_pool.extend(new_working)
                logger.info(f"Live working pool: {len(self.working_pool)} ready.")
        finally:
            with self.lock:
                self.is_refreshing = False

    def get_next_working_proxy(self) -> str:
        """Pulls a verified working proxy from the pool, refreshing in background if low."""
        with self.lock:
            if len(self.working_pool) < 5 and not self.is_refreshing:
                threading.Thread(target=self.refresh_working_pool, args=(15,), daemon=True).start()

            if self.working_pool:
                proxy = self.working_pool.pop(0)
                self.used_proxies.add(proxy)
                return proxy

        # If pool was empty, try a quick synchronous refresh
        self.refresh_working_pool(target_count=10)
        with self.lock:
            if self.working_pool:
                proxy = self.working_pool.pop(0)
                self.used_proxies.add(proxy)
                return proxy

        # Fallback to direct connection if none ready yet
        return "direct"

    def apply_proxy_to_device(self, adb_bin: str, device_id: str, proxy: str) -> bool:
        """Sets Android global http_proxy on the device via ADB."""
        try:
            from airplane_mode import get_device_port
            port = get_device_port(device_id)
            base_cmd = [adb_bin]
            if port != 5037:
                base_cmd.extend(["-P", str(port)])
            if device_id:
                base_cmd.extend(["-s", device_id])

            if not proxy or proxy == "direct":
                subprocess.run(base_cmd + ["shell", "settings", "put", "global", "http_proxy", ":0"],
                               check=True, timeout=3, stdout=subprocess.DEVNULL)
                logger.info(f"[{device_id}] Proxy set to Direct (no proxy).")
                self.device_current_proxy[device_id] = None
                return True

            subprocess.run(base_cmd + ["shell", "settings", "put", "global", "http_proxy", proxy],
                           check=True, timeout=3, stdout=subprocess.DEVNULL)
            logger.info(f"[{device_id}] Applied Rotating Proxy: {proxy}")
            self.device_current_proxy[device_id] = proxy
            return True
        except Exception as e:
            logger.error(f"[{device_id}] Error setting proxy {proxy}: {e}")
            return False

    def clear_device_proxy(self, adb_bin: str, device_id: str):
        """Removes proxy settings from Android instance."""
        try:
            from airplane_mode import get_device_port
            port = get_device_port(device_id)
            base_cmd = [adb_bin]
            if port != 5037:
                base_cmd.extend(["-P", str(port)])
            if device_id:
                base_cmd.extend(["-s", device_id])
            subprocess.run(base_cmd + ["shell", "settings", "put", "global", "http_proxy", ":0"],
                           timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        self.device_current_proxy.pop(device_id, None)

    def rotate_device_ip(self, adb_bin: str, device_id: str) -> str:
        """Picks a fresh verified proxy and applies it to the device."""
        proxy = self.get_next_working_proxy()
        self.apply_proxy_to_device(adb_bin, device_id, proxy)
        return proxy


_GLOBAL_ROTATOR = None
_ROTATOR_LOCK = threading.Lock()


def get_global_proxy_rotator() -> GitHubProxyRotator:
    global _GLOBAL_ROTATOR
    with _ROTATOR_LOCK:
        if _GLOBAL_ROTATOR is None:
            _GLOBAL_ROTATOR = GitHubProxyRotator()
            _GLOBAL_ROTATOR.refresh_working_pool(target_count=10)
        return _GLOBAL_ROTATOR


def is_mobile_rotator_available() -> tuple[bool, str | None]:
    """
    Checks if a physical mobile device with cellular connectivity is connected.
    Ignores MEmu/emulator instances (127.0.0.1:xxxxx or emulator-xxxx).
    """
    try:
        from airplane_mode import ADB_BIN
        cmd = [ADB_BIN, "devices"]
        out = subprocess.check_output(cmd, text=True, timeout=3)
        for line in out.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                if not serial.startswith("127.0.0.1:") and not serial.startswith("emulator-"):
                    return True, serial
    except Exception:
        pass
    return False, None


def rotate_ip_smart(device_id: str = None, airplane_delay: float = 1.5) -> str:
    """
    Intelligent IP Rotator:
    - If a physical mobile device (e.g. Vivo) is available:
      Uses toggle_airplane_mode for fast 4G LTE IP rotation.
    - If NO mobile device is available:
      Checks config.json: if use_github_proxy is True, rotates via GitHub Public Proxies;
      otherwise maintains stable direct broadband (:0).
    """
    has_mobile, mobile_id = is_mobile_rotator_available()
    if has_mobile:
        from airplane_mode import toggle_airplane_mode
        print(f"[*] Physical mobile detected ({mobile_id}). Rotating IP via Airplane Mode...")
        toggle_airplane_mode(airplane_delay, mobile_id)
        return f"Mobile_{mobile_id}"
    else:
        # Check if user enabled GitHub public proxy in config
        use_proxy = False
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    use_proxy = cfg.get("use_github_proxy", False)
        except Exception:
            pass

        from airplane_mode import ADB_BIN
        if not use_proxy:
            print(f"[*] Mobile not attached. Using Direct Fast Connection (:0) for {device_id}...")
            if device_id:
                try:
                    subprocess.run([ADB_BIN, "-s", device_id, "shell", "settings", "put", "global", "http_proxy", ":0"],
                                   timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            return "Direct_Broadband"

        # Fallback to GitHub proxy rotation for the emulator
        print(f"[*] Mobile not available. Rotating IP via GitHub Public Proxy Pool for {device_id}...")
        rotator = get_global_proxy_rotator()
        assigned_proxy = rotator.rotate_device_ip(ADB_BIN, device_id)
        print(f"[+] GitHub Proxy assigned to {device_id}: {assigned_proxy}")
        return assigned_proxy


if __name__ == "__main__":
    rotator = GitHubProxyRotator()
    rotator.refresh_working_pool(target_count=5)
    print("\nVerified Working Proxies Ready:")
    for i in range(min(5, len(rotator.working_pool))):
        print(f"  [{i+1}] {rotator.get_next_working_proxy()}")
