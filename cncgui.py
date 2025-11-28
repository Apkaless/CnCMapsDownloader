import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import requests
import bs4
import os
import time
import re
import random
import concurrent.futures
from random import choice
from PIL import Image, ImageTk
import base64
from io import BytesIO


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
        self.is_running = False
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()

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
                    if self.log_callback:
                        self.log_callback(f"[429] Waiting {backoff_factor:.1f}s (attempt {attempt})", "warning")
                    time.sleep(backoff_factor)
                    last_exc = Exception("429")
                    continue
                if 500 <= resp.status_code < 600:
                    backoff_factor = min(60, (2 ** attempt) + random.uniform(0, 1.5))
                    if self.log_callback:
                        self.log_callback(f"[{resp.status_code}] Server error. Waiting {backoff_factor:.1f}s", "warning")
                    time.sleep(backoff_factor)
                    last_exc = Exception(str(resp.status_code))
                    continue
                return resp
            except requests.RequestException as e:
                last_exc = e
                backoff_factor = min(60, (2 ** attempt) + random.uniform(0, 1.5))
                if self.log_callback:
                    self.log_callback(f"Request exception: {e}. Retrying in {backoff_factor:.1f}s", "warning")
                time.sleep(backoff_factor)
        raise last_exc if last_exc else Exception("Request failed")

    @staticmethod
    def get_maps_urls(html_content: str):
        soup = bs4.BeautifulSoup(html_content, 'lxml')
        elements = soup.find_all('a', class_='DisplayName')
        return elements if elements else []

    @staticmethod
    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[\\/:"*?<>|]+', '_', name).strip()
        return name[:200] if len(name) > 200 else name

    def download_map(self, map_info: dict) -> tuple[str, bool, str]:
        if not self.is_running:
            return (map_info['Name'], False, "Stopped by user")
            
        map_name = map_info['Name']
        map_url = map_info['DownloadUrl']
        filename = self.sanitize_filename(map_name) + '.zip'
        target_path = os.path.join(self.download_dir, filename)
        
        if os.path.exists(target_path):
            msg = f"Skipped (exists)"
            if self.log_callback:
                self.log_callback(f"[SKIP] {map_name}", "warning")
            return (map_name, True, msg)
        
        try:
            r = self.request_with_backoff(map_url, stream=True)
            total_size = int(r.headers.get('Content-Length', 0) or 0)
            downloaded = 0
            
            with open(target_path + '.part', 'wb') as f:
                for chunk in r.iter_content(8192):
                    if not self.is_running:
                        os.remove(target_path + '.part')
                        return (map_name, False, "Stopped by user")
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if self.progress_callback and total_size > 0:
                            percent = min(100, downloaded * 100 / total_size)
                            self.progress_callback(map_name, percent)
            
            os.replace(target_path + '.part', target_path)
            msg = f"Downloaded successfully"
            if self.log_callback:
                self.log_callback(f"[OK] {map_name}", "success")
            return (map_name, True, target_path)
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"[ERROR] {map_name}: {str(e)}", "error")
            return (map_name, False, str(e))

    def download_all_maps(self):
        self.is_running = True
        page = 1
        total_downloaded = 0
        
        while page <= self.max_pages and self.is_running:
            url = f"{self.BASE_URL}/maps/generals/zerohour-maps.aspx?page={page}&players={self.players}"
            try:
                if self.log_callback:
                    self.log_callback(f"[INFO] Processing page {page}/{self.max_pages}", "info")
                
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
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        futures = [executor.submit(self.download_map, m) for m in maps_list]
                        for fut in concurrent.futures.as_completed(futures):
                            if not self.is_running:
                                break
                            name, ok, msg = fut.result()
                            if ok:
                                total_downloaded += 1
                else:
                    if self.log_callback:
                        self.log_callback(f"[INFO] No maps found on page {page}", "info")
                        
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"[ERROR] Page {page}: {e}", "error")
            
            page += 1
            if self.is_running and page <= self.max_pages:
                time.sleep(random.uniform(2, 5))
        
        if self.log_callback:
            if self.is_running:
                self.log_callback(f"\n[DONE] Download completed! Total maps: {total_downloaded}", "success")
            else:
                self.log_callback(f"\n[STOPPED] Process stopped by user. Downloaded: {total_downloaded}", "warning")
        
        self.is_running = False

    def stop(self):
        self.is_running = False


class CnCLabsGUI:
    def load_icon(self):
        """Load the icon image - tries to find icon.png in the same directory"""
        try:
            # Try to load icon from file
            icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                img = img.resize((70, 70), Image.LANCZOS)
                self.icon_image = ImageTk.PhotoImage(img)
            else:
                # Icon file not found, will use emoji fallback
                self.icon_image = None
        except Exception as e:
            print(f"Could not load icon: {e}")
            self.icon_image = None
    
    def __init__(self, root):
        self.root = root
        self.root.title("CNC Labs Map Downloader - Generals Zero Hour")
        self.root.geometry("950x750")
        
        # Colors matching Generals Zero Hour icon (blue theme)
        self.bg_dark = "#000000"  # Dark navy blue
        self.bg_medium = "#000000"  # Medium blue
        self.bg_light = "#000000"  # Light blue
        self.accent_light = "#01B7FF"  # Sky blue
        self.accent_bright = "#000000"  # Deep sky blue
        self.text_white = "#01B7FF"  # White
        self.text_light_blue = "#00101F"  # Very light blue
        self.silver = "#C0C0C0"  # Silver/steel color
        
        self.root.configure(bg=self.bg_dark)
        
        self.downloader = None
        self.download_thread = None
        self.icon_image = None
        
        self.load_icon()
        self.setup_ui()
        
    def load_icon(self):
        """Load the icon image - tries to find icon.png in the same directory"""
        try:
            # Try to load icon from file
            icon_path = os.path.join(os.path.dirname(__file__), "icon.jpg")
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                img = img.resize((70, 70), Image.LANCZOS)
                self.icon_image = ImageTk.PhotoImage(img)
            else:
                # Icon file not found, will use emoji fallback
                self.icon_image = None
        except Exception as e:
            print(f"Could not load icon: {e}")
            self.icon_image = None
        
    def setup_ui(self):
        # Header Frame with gradient effect
        header_frame = tk.Frame(self.root, bg=self.bg_medium, relief=tk.RAISED, bd=4)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Icon and Title Container
        title_container = tk.Frame(header_frame, bg=self.bg_medium)
        title_container.pack(pady=15)
        
        # Icon placeholder - you can add actual image here
        icon_frame = tk.Frame(title_container, bg=self.bg_dark, width=80, height=80, relief=tk.RIDGE, bd=3)
        icon_frame.pack(side=tk.LEFT, padx=15)
        icon_frame.pack_propagate(False)
        
        if self.icon_image:
            # Display the actual icon image
            icon_label = tk.Label(
                icon_frame,
                image=self.icon_image,
                bg=self.bg_dark
            )
            icon_label.pack(expand=True)
        else:
            # Fallback to emoji if icon not found
            icon_label = tk.Label(
                icon_frame,
                text="⚔️",
                font=("Arial", 40),
                bg=self.bg_dark,
                fg=self.accent_light
            )
            icon_label.pack(expand=True)
        
        # Title text
        title_text_frame = tk.Frame(title_container, bg=self.bg_medium)
        title_text_frame.pack(side=tk.LEFT, padx=10)
        
        title_label = tk.Label(
            title_text_frame,
            text="CNC LABS MAP DOWNLOADER",
            font=("Arial Black", 22, "bold"),
            bg=self.bg_medium,
            fg=self.text_white
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_text_frame,
            text="COMMAND & CONQUER: GENERALS ZERO HOUR",
            font=("Arial", 11, "bold"),
            bg=self.bg_medium,
            fg=self.accent_light
        )
        subtitle_label.pack()
        
        # Settings Frame
        settings_frame = tk.LabelFrame(
            self.root,
            text=" ⚙ CONFIGURATION ",
            font=("Arial", 12, "bold"),
            bg=self.bg_light,
            fg=self.text_white,
            relief=tk.GROOVE,
            bd=4
        )
        settings_frame.pack(fill=tk.X, padx=10, pady=8)
        
        # Settings Grid
        settings_inner = tk.Frame(settings_frame, bg=self.bg_light)
        settings_inner.pack(padx=15, pady=12)
        
        # Players
        tk.Label(
            settings_inner,
            text="Number of Players:",
            bg=self.bg_light,
            fg=self.text_white,
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        
        self.players_var = tk.IntVar(value=8)
        players_spinbox = tk.Spinbox(
            settings_inner,
            from_=2,
            to=8,
            textvariable=self.players_var,
            width=12,
            font=("Arial", 10, "bold"),
            bg=self.bg_dark,
            fg=self.accent_light,
            buttonbackground=self.accent_bright,
            relief=tk.SUNKEN,
            bd=2
        )
        players_spinbox.grid(row=0, column=1, padx=8, pady=6)
        
        # Max Pages
        tk.Label(
            settings_inner,
            text="Max Pages:",
            bg=self.bg_light,
            fg=self.text_white,
            font=("Arial", 10, "bold")
        ).grid(row=0, column=2, sticky=tk.W, padx=8, pady=6)
        
        self.max_pages_var = tk.IntVar(value=10)
        pages_spinbox = tk.Spinbox(
            settings_inner,
            from_=1,
            to=100,
            textvariable=self.max_pages_var,
            width=12,
            font=("Arial", 10, "bold"),
            bg=self.bg_dark,
            fg=self.accent_light,
            buttonbackground=self.accent_bright,
            relief=tk.SUNKEN,
            bd=2
        )
        pages_spinbox.grid(row=0, column=3, padx=8, pady=6)
        
        # Workers
        tk.Label(
            settings_inner,
            text="Parallel Downloads:",
            bg=self.bg_light,
            fg=self.text_white,
            font=("Arial", 10, "bold")
        ).grid(row=1, column=0, sticky=tk.W, padx=8, pady=6)
        
        self.workers_var = tk.IntVar(value=3)
        workers_spinbox = tk.Spinbox(
            settings_inner,
            from_=1,
            to=10,
            textvariable=self.workers_var,
            width=12,
            font=("Arial", 10, "bold"),
            bg=self.bg_dark,
            fg=self.accent_light,
            buttonbackground=self.accent_bright,
            relief=tk.SUNKEN,
            bd=2
        )
        workers_spinbox.grid(row=1, column=1, padx=8, pady=6)
        
        # Download Directory
        tk.Label(
            settings_inner,
            text="Download Directory:",
            bg=self.bg_light,
            fg=self.text_white,
            font=("Arial", 10, "bold")
        ).grid(row=2, column=0, sticky=tk.W, padx=8, pady=6)
        
        dir_frame = tk.Frame(settings_inner, bg=self.bg_light)
        dir_frame.grid(row=2, column=1, columnspan=3, sticky=tk.EW, padx=8, pady=6)
        
        self.dir_var = tk.StringVar(value="downloads")
        dir_entry = tk.Entry(
            dir_frame,
            textvariable=self.dir_var,
            font=("Arial", 10),
            bg=self.bg_dark,
            fg=self.accent_light,
            width=35,
            relief=tk.SUNKEN,
            bd=2
        )
        dir_entry.pack(side=tk.LEFT, padx=(0, 8))
        
        browse_btn = tk.Button(
            dir_frame,
            text="📁 Browse",
            command=self.browse_directory,
            bg=self.accent_bright,
            fg=self.text_white,
            font=("Arial", 9, "bold"),
            relief=tk.RAISED,
            bd=3,
            activebackground=self.accent_light
        )
        browse_btn.pack(side=tk.LEFT)
        
        # Progress Frame
        progress_frame = tk.LabelFrame(
            self.root,
            text=" 📊 PROGRESS ",
            font=("Arial", 12, "bold"),
            bg=self.bg_light,
            fg=self.text_white,
            relief=tk.GROOVE,
            bd=4
        )
        progress_frame.pack(fill=tk.X, padx=10, pady=8)
        
        progress_inner = tk.Frame(progress_frame, bg=self.bg_light)
        progress_inner.pack(padx=15, pady=12, fill=tk.X)
        
        self.progress_label = tk.Label(
            progress_inner,
            text="⏸ Ready to start download",
            bg=self.bg_light,
            fg=self.text_white,
            font=("Arial", 11, "bold")
        )
        self.progress_label.pack(pady=(0, 8))
        
        # Custom styled progress bar
        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Custom.Horizontal.TProgressbar",
            thickness=28,
            troughcolor=self.bg_dark,
            background=self.accent_bright,
            bordercolor=self.bg_medium,
            lightcolor=self.accent_light,
            darkcolor=self.bg_medium
        )
        
        self.progress_bar = ttk.Progressbar(
            progress_inner,
            length=500,
            mode='indeterminate',
            style="Custom.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Control Buttons Frame
        control_frame = tk.Frame(self.root, bg=self.bg_dark)
        control_frame.pack(pady=12)
        
        # Start Button
        self.start_btn = tk.Button(
            control_frame,
            text="▶ START DOWNLOAD",
            command=self.start_download,
            bg=self.accent_bright,
            fg=self.text_white,
            font=("Arial Black", 13, "bold"),
            width=22,
            height=2,
            relief=tk.RAISED,
            bd=4,
            activebackground=self.accent_light,
            activeforeground=self.text_white,
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.LEFT, padx=8)
        
        # Stop Button
        self.stop_btn = tk.Button(
            control_frame,
            text="■ STOP",
            command=self.stop_download,
            bg=self.silver,
            fg=self.bg_dark,
            font=("Arial Black", 13, "bold"),
            width=12,
            height=2,
            relief=tk.RAISED,
            bd=4,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=8)
        
        # Logs Frame
        logs_frame = tk.LabelFrame(
            self.root,
            text=" 📋 DOWNLOAD LOGS ",
            font=("Arial", 12, "bold"),
            bg=self.bg_light,
            fg=self.text_white,
            relief=tk.GROOVE,
            bd=4
        )
        logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Log text widget with custom styling
        self.log_text = scrolledtext.ScrolledText(
            logs_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#001a33",  # Very dark blue
            fg=self.accent_light,
            height=16,
            relief=tk.SUNKEN,
            bd=2
        )
        self.log_text.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)
        
        # Configure text tags for colored logs
        self.log_text.tag_config("success", foreground="#00FF00")  # Bright green
        self.log_text.tag_config("error", foreground="#FF3333")  # Bright red
        self.log_text.tag_config("warning", foreground="#FFAA00")  # Orange
        self.log_text.tag_config("info", foreground=self.accent_light)  # Sky blue
        
        # Add initial welcome message
        welcome_msg = """
╔══════════════════════════════════════════════════════════════════════╗
║   WELCOME TO CNC LABS MAP DOWNLOADER                                 ║
║   Configure your settings above and click START DOWNLOAD to begin    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
        self.log_text.insert(tk.END, welcome_msg, "info")
        
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)
    
    def log_message(self, message, log_type="info"):
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, full_message, log_type)
        self.log_text.see(tk.END)
    
    def update_progress(self, map_name, percent):
        self.progress_label.config(text=f"⬇ Downloading: {map_name} - {percent:.1f}%")
    
    def start_download(self):
        if self.download_thread and self.download_thread.is_alive():
            messagebox.showwarning("Warning", "Download is already running!")
            return
        
        self.start_btn.config(state=tk.DISABLED, bg=self.silver)
        self.stop_btn.config(state=tk.NORMAL, bg="#FF4444", activebackground="#FF6666")
        self.log_text.delete(1.0, tk.END)
        self.progress_bar.start(10)
        
        self.downloader = CnCLabsDownloader(
            players=self.players_var.get(),
            max_pages=self.max_pages_var.get(),
            download_dir=self.dir_var.get(),
            max_workers=self.workers_var.get(),
            log_callback=self.log_message,
            progress_callback=self.update_progress
        )
        
        self.download_thread = threading.Thread(target=self.run_download, daemon=True)
        self.download_thread.start()
    
    def run_download(self):
        try:
            self.downloader.download_all_maps()
        except Exception as e:
            self.log_message(f"Fatal error: {str(e)}", "error")
        finally:
            self.progress_bar.stop()
            self.start_btn.config(state=tk.NORMAL, bg=self.accent_bright)
            self.stop_btn.config(state=tk.DISABLED, bg=self.silver)
            self.progress_label.config(text="✓ Download complete")
    
    def stop_download(self):
        if self.downloader:
            self.downloader.stop()
            self.log_message("⏹ Stopping download process...", "warning")
            self.stop_btn.config(state=tk.DISABLED)


def main():
    root = tk.Tk()
    app = CnCLabsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()