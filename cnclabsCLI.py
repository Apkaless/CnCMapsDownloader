import requests
import bs4
import os
import sys
import time
import re
import random
import concurrent.futures
from colorama import init, Fore, Style
from random import choice
import argparse

init(autoreset=True)


class CnCLabsDownloader:
    BASE_URL = 'https://www.cnclabs.com'
    USER_AGENTS = [
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.94 Chrome/37.0.2062.94 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
    ]

    def __init__(self, players: int = 8, max_pages: int = 10, download_dir: str = "downloads", max_workers: int = 3,
                 log_callback=None, progress_callback=None):
        self.players = players
        self.max_pages = max_pages
        self.download_dir = download_dir
        self.max_workers = max_workers
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()

    # الطلب مع backoff
    def request_with_backoff(self, url: str, max_attempts: int = 5, **kwargs):
        attempt = 0
        last_exc = None
        while attempt < max_attempts:
            attempt += 1
            try:
                self.session.headers.update({'user-agent': choice(self.USER_AGENTS)})
                resp = self.session.get(url, **kwargs)
                if resp.status_code == 429:
                    backoff_factor = min(60, (2 ** attempt) + random.uniform(0, 1.5))
                    print(Fore.YELLOW + f"[429] Waiting {backoff_factor:.1f}s (attempt {attempt})" + Style.RESET_ALL)
                    time.sleep(backoff_factor)
                    last_exc = Exception("429")
                    continue
                if 500 <= resp.status_code < 600:
                    backoff_factor = min(60, (2 ** attempt) + random.uniform(0, 1.5))
                    print(Fore.YELLOW + f"[{resp.status_code}] Server error. Waiting {backoff_factor:.1f}s" + Style.RESET_ALL)
                    time.sleep(backoff_factor)
                    last_exc = Exception(str(resp.status_code))
                    continue
                return resp
            except requests.RequestException as e:
                last_exc = e
                backoff_factor = min(60, (2 ** attempt) + random.uniform(0, 1.5))
                print(Fore.YELLOW + f"Request exception: {e}. Retrying in {backoff_factor:.1f}s" + Style.RESET_ALL)
                time.sleep(backoff_factor)
        raise last_exc if last_exc else Exception("Request failed")

    # استخراج روابط الخرائط من الصفحة
    @staticmethod
    def get_maps_urls(html_content: str):
        soup = bs4.BeautifulSoup(html_content, 'lxml')
        elements = soup.find_all('a', class_='DisplayName')
        return elements if elements else []

    # تنظيف اسم الملف
    @staticmethod
    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[\\/:"*?<>|]+', '_', name).strip()
        return name[:200] if len(name) > 200 else name

    # تحميل الخريطة بشكل متدرج
    def download_map(self, map_info: dict) -> tuple[str, bool, str]:
        map_name = map_info['Name']
        map_url = map_info['DownloadUrl']
        filename = self.sanitize_filename(map_name) + '.zip'
        target_path = os.path.join(self.download_dir, filename)
        if os.path.exists(target_path):
            msg = f"Skipped (exists) {target_path}"
            return (map_name, True, msg)
        try:
            r = self.request_with_backoff(map_url, stream=True)
            total_size = int(r.headers.get('Content-Length', 0) or 0)
            downloaded = 0 # bytes
            with open(target_path + '.part', 'wb') as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.print_progress(map_name, downloaded, total_size)
            os.replace(target_path + '.part', target_path)
            msg = f"Downloaded: {target_path}"
            try:
                print(Fore.GREEN + f"\n{msg}" + Style.RESET_ALL)
            except Exception:
                pass
            return (map_name, True, target_path)
        except Exception as e:
            return (map_name, False, str(e))

    def print_progress(self, name, downloaded, total):
        if total > 0:
            percent = min(100, downloaded * 100 / total)
            bar_len = 40
            filled = int(bar_len * percent / 100)
            bar = Fore.GREEN + '=' * filled + Style.DIM + ' ' * (bar_len - filled) + Style.RESET_ALL
            text = f"\r{Fore.CYAN}Downloading {name} {bar} {percent:.1f}%"
            try:
                # print to stdout for CLI compatibility
                sys.stdout.write(text)
                sys.stdout.flush()
            except Exception:
                pass

    # تحميل جميع الخرائط
    def download_all_maps(self):
        page = 1
        while page <= self.max_pages:
            url = f"{self.BASE_URL}/maps/generals/zerohour-maps.aspx?page={page}&players={self.players}"
            try:
                resp = self.request_with_backoff(url)
                elements = self.get_maps_urls(resp.text)
                if elements:
                    maps_list = []
                    for e in elements:
                        maps_list.append({
                            'Name': e.get_text(),
                            'Players': self.players,
                            'DownloadUrl': self.BASE_URL + e['href'].replace('details', 'fetch')
                        })
                    # تحميل بالتوازي
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        futures = [executor.submit(self.download_map, m) for m in maps_list]
                        for fut in concurrent.futures.as_completed(futures):
                            name, ok, msg = fut.result()
                            color = Fore.GREEN if ok else Fore.RED
                            try:
                                print(color + f"[{'OK' if ok else 'FAIL'}] {name}: {msg}" + Style.RESET_ALL)
                            except Exception:
                                pass
            except Exception as e:
                try:
                    print(Fore.RED + f"[ERROR] Page {page}: {e}" + Style.RESET_ALL)
                except Exception:
                    pass
                if callable(self.log_callback):
                    try:
                        self.log_callback('page', False, f'Page {page}: {e}')
                    except Exception:
                        pass
            page += 1
            time.sleep(random.uniform(2, 5))


def main():
    parser = argparse.ArgumentParser(description="CNC Labs Map Downloader CLI")
    parser.add_argument('-p', '--players', type=int, default=8, help="Number of players")
    parser.add_argument('-m', '--max-pages', type=int, default=10, help="Maximum number of pages to scrape")
    parser.add_argument('-w', '--workers', type=int, default=3, help="Number of parallel downloads")
    parser.add_argument('-d', '--dir', type=str, default='downloads', help="Download directory")
    args = parser.parse_args()

    downloader = CnCLabsDownloader(
        players=args.players,
        max_pages=args.max_pages,
        max_workers=args.workers,
        download_dir=args.dir
    )
    downloader.download_all_maps()


if __name__ == "__main__":
    main()
