from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

ROOT_DIR = Path(__file__).resolve().parent
CASCADE_PROJECTS_DIR = ROOT_DIR.parent
JUKEBOX_DIR = CASCADE_PROJECTS_DIR / 'BARD JUKEBOX 1.0'
VISUALIZER_DIR = ROOT_DIR

JUKEBOX_URL = 'http://127.0.0.1:8765/player'
VISUALIZER_CONTROLLER_URL = 'http://127.0.0.1:4173/?channel=bard-main'
VISUALIZER_OBS_URL = 'http://127.0.0.1:4173/?display=obs&channel=bard-main'

BG_COLOR = '#2a2a2f'
PANEL_COLOR = '#38383f'
ACCENT_COLOR = '#f08c2e'
TEXT_COLOR = '#e4e4e6'
BUTTON_COLOR = '#f08c2e'
BUTTON_ACTIVE_COLOR = '#ff9d3a'
ENTRY_COLOR = '#45454d'
DISABLED_BUTTON_COLOR = '#6a533c'
DISABLED_TEXT_COLOR = '#9a9aa3'
BORDER_COLOR = '#6b6b75'
BUTTON_TEXT_COLOR = '#101010'
PLAYBACK_PANEL_COLOR = '#40363a'

if sys.platform == 'win32':
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    PROCESS_FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
else:
    PROCESS_FLAGS = 0


class BardControlCenter:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('Bard Control Center')
        self.root.geometry('760x840')
        self.root.minsize(700, 520)
        self.root.configure(bg=BG_COLOR)

        self.jukebox_process: subprocess.Popen[str] | None = None
        self.visualizer_process: subprocess.Popen[str] | None = None

        self.status_message = tk.StringVar(value='Ready.')
        self.jukebox_status = tk.StringVar(value='Stopped')
        self.visualizer_status = tk.StringVar(value='Stopped')
        self.controller_url = tk.StringVar(value=VISUALIZER_CONTROLLER_URL)
        self.obs_url = tk.StringVar(value=VISUALIZER_OBS_URL)
        self.jukebox_url = tk.StringVar(value=JUKEBOX_URL)
        self.urls_visible = True
        self.url_visibility_text = tk.StringVar(value='Hide All Links')
        self.display_controller_url = tk.StringVar(value=VISUALIZER_CONTROLLER_URL)
        self.display_obs_url = tk.StringVar(value=VISUALIZER_OBS_URL)
        self.display_jukebox_url = tk.StringVar(value=JUKEBOX_URL)

        self._build_ui()
        self._start_status_loop()

    def _style_button(self, button: tk.Button, enabled: bool = True) -> None:
        button.configure(
            bg=BUTTON_COLOR if enabled else DISABLED_BUTTON_COLOR,
            activebackground=BUTTON_ACTIVE_COLOR if enabled else DISABLED_BUTTON_COLOR,
            fg=BUTTON_TEXT_COLOR if enabled else DISABLED_TEXT_COLOR,
            activeforeground=BUTTON_TEXT_COLOR if enabled else DISABLED_TEXT_COLOR,
            disabledforeground=DISABLED_TEXT_COLOR,
            relief='solid',
            bd=2,
            padx=8,
            pady=6,
            highlightthickness=2,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
            font=('Segoe UI', 10, 'bold'),
            cursor='hand2' if enabled else 'arrow',
        )

    def _make_button(self, parent, text: str, width: int, command=None, enabled: bool = True) -> tk.Button:
        state = 'normal' if enabled else 'disabled'
        button = tk.Button(parent, text=text, width=width, command=command, state=state)
        self._style_button(button, enabled=enabled)
        return button

    def _build_ui(self) -> None:
        outer_frame = tk.Frame(self.root, bg=BG_COLOR)
        outer_frame.pack(fill='both', expand=True)

        canvas = tk.Canvas(outer_frame, highlightthickness=0, bg=BG_COLOR)
        scrollbar = tk.Scrollbar(
            outer_frame,
            orient='vertical',
            command=canvas.yview,
            activebackground=BUTTON_ACTIVE_COLOR,
            troughcolor=PANEL_COLOR,
            bg=BUTTON_COLOR,
            elementborderwidth=2,
            borderwidth=2,
            relief='solid',
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        frame = tk.Frame(canvas, padx=18, pady=18, bg=BG_COLOR)
        canvas_window = canvas.create_window((0, 0), window=frame, anchor='nw')

        def sync_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox('all'))

        def sync_inner_width(event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        def on_mousewheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        frame.bind('<Configure>', sync_scroll_region)
        canvas.bind('<Configure>', sync_inner_width)
        canvas.bind_all('<MouseWheel>', on_mousewheel)

        title = tk.Label(frame, text='Bard Control Center', font=('Segoe UI', 18, 'bold'), bg=BG_COLOR, fg=ACCENT_COLOR)
        title.pack(anchor='w')

        subtitle = tk.Label(
            frame,
            text='Launch the jukebox and visualizer without typing commands.',
            font=('Segoe UI', 10),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        )
        subtitle.pack(anchor='w', pady=(4, 16))

        quick_box = tk.LabelFrame(frame, text='Quick Start', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        quick_box.pack(fill='x')

        self._make_button(quick_box, 'Start Bard System', 22, self.start_bard_system).grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Start + Open Everything', 22, self.start_and_open_everything).grid(row=0, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Open Controller + Player', 22, self.open_main_pages).grid(row=0, column=2, pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Stop All', 22, self.stop_all).grid(row=1, column=0, padx=(0, 10), sticky='w')
        self._make_button(quick_box, 'Copy OBS URL', 22, self.copy_obs_url).grid(row=1, column=1, padx=(0, 10), sticky='w')
        self._make_button(quick_box, 'Open OBS Visualizer URL', 22, lambda: self.open_url(self.obs_url.get())).grid(row=1, column=2, sticky='w')

        status_box = tk.LabelFrame(frame, text='Status', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        status_box.pack(fill='x')

        tk.Label(status_box, text='Jukebox:', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, sticky='w')
        tk.Label(status_box, textvariable=self.jukebox_status, bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=1, sticky='w', padx=(8, 0))
        tk.Label(status_box, text='Visualizer:', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky='w', pady=(6, 0))
        tk.Label(status_box, textvariable=self.visualizer_status, bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(6, 0))

        launch_box = tk.LabelFrame(frame, text='Services', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        launch_box.pack(fill='x', pady=(14, 0))

        self._make_button(launch_box, 'Start Jukebox', 24, self.start_jukebox).grid(row=1, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(launch_box, 'Start Visualizer', 24, self.start_visualizer).grid(row=1, column=1, pady=(0, 8), sticky='w')

        links_box = tk.LabelFrame(frame, text='Open Pages', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        links_box.pack(fill='x', pady=(14, 0))

        self._make_button(links_box, 'Open Jukebox Player', 24, lambda: self.open_url(self.jukebox_url.get())).grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(links_box, 'Open Visualizer Controller', 24, lambda: self.open_url(self.controller_url.get())).grid(row=0, column=1, pady=(0, 8), sticky='w')
        self._make_button(links_box, 'Open Jukebox + Controller', 24, self.open_main_pages).grid(row=1, column=0, padx=(0, 10), sticky='w')
        self._make_button(links_box, 'Open OBS Visualizer URL', 24, lambda: self.open_url(self.obs_url.get())).grid(row=1, column=1, sticky='w')

        urls_box = tk.LabelFrame(frame, text='URLs', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        urls_box.pack(fill='x', pady=(14, 0))

        toggle_links_button = self._make_button(urls_box, '', 10, self.toggle_urls_visibility)
        toggle_links_button.configure(textvariable=self.url_visibility_text)
        toggle_links_button.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))

        tk.Label(urls_box, text='Jukebox Player', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky='w')
        tk.Entry(urls_box, textvariable=self.display_jukebox_url, width=72, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=1, column=1, padx=(10, 10), sticky='we')
        self._make_button(urls_box, 'Copy', 10, lambda: self.copy_text(self.jukebox_url.get(), 'Copied jukebox player URL.')).grid(row=1, column=3, sticky='e')

        tk.Label(urls_box, text='Visualizer Controller', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, sticky='w', pady=(8, 0))
        tk.Entry(urls_box, textvariable=self.display_controller_url, width=72, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=2, column=1, padx=(10, 10), pady=(8, 0), sticky='we')
        self._make_button(urls_box, 'Copy', 10, lambda: self.copy_text(self.controller_url.get(), 'Copied controller URL.')).grid(row=2, column=3, pady=(8, 0), sticky='e')

        tk.Label(urls_box, text='OBS Visualizer', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=3, column=0, sticky='w', pady=(8, 0))
        tk.Entry(urls_box, textvariable=self.display_obs_url, width=72, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=3, column=1, padx=(10, 10), pady=(8, 0), sticky='we')
        self._make_button(urls_box, 'Copy', 10, self.copy_obs_url).grid(row=3, column=3, pady=(8, 0), sticky='e')

        urls_box.grid_columnconfigure(1, weight=1)

        notes_box = tk.LabelFrame(frame, text='Notes', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        notes_box.pack(fill='both', expand=True, pady=(14, 0))

        notes = (
            'Current easy flow:\n'
            '1. Click Start + Open Everything\n'
            '2. In the controller tab, click Connect audio\n'
            '3. In OBS, use the OBS Visualizer URL as a Browser Source\n'
            '4. Keep the controller tab available while streaming\n\n'
            'If the visualizer only updates while its tab is active, that is usually browser throttling.\n'
            'For now, keep the controller tab visible during use. A more robust future fix would move capture/control into a desktop wrapper.'
        )
        tk.Label(notes_box, text=notes, justify='left', anchor='w', bg=PANEL_COLOR, fg=TEXT_COLOR).pack(fill='both', expand=True)

        future_box = tk.LabelFrame(frame, text='To Eventually Set Up', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        future_box.pack(fill='x', pady=(14, 0))

        tk.Label(
            future_box,
            text='These are visual placeholders only for planned stream controls. They do not do anything yet.',
            justify='left',
            anchor='w',
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        self._make_button(future_box, 'Adult On', 20, enabled=False).grid(row=1, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Adult Off', 20, enabled=False).grid(row=1, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Only BEST', 20, enabled=False).grid(row=1, column=2, pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Only Music', 20, enabled=False).grid(row=2, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Only Clips', 20, enabled=False).grid(row=2, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'No Clips', 20, enabled=False).grid(row=2, column=2, pady=(0, 8), sticky='w')

        playback_box = tk.LabelFrame(frame, text='Playback Controls Eventually', padx=12, pady=10, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        playback_box.pack(fill='x', pady=(14, 0))

        tk.Label(
            playback_box,
            text='Future playback controls for stream management.',
            justify='left',
            anchor='w',
            bg=PLAYBACK_PANEL_COLOR,
            fg=TEXT_COLOR,
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        playback_shell = tk.Frame(playback_box, bg=PLAYBACK_PANEL_COLOR)
        playback_shell.grid(row=1, column=0, columnspan=3, sticky='ew')
        playback_shell.grid_columnconfigure(0, weight=0)
        playback_shell.grid_columnconfigure(1, weight=1)
        playback_shell.grid_columnconfigure(2, weight=0)

        speed_down_box = tk.LabelFrame(playback_shell, text='Speed', padx=8, pady=8, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        speed_down_box.grid(row=0, column=0, sticky='nsw', padx=(0, 8))
        self._make_button(speed_down_box, '< 0.25x', 8, enabled=False).grid(row=0, column=0, sticky='ew')

        playback_center_box = tk.Frame(playback_shell, bg=PLAYBACK_PANEL_COLOR)
        playback_center_box.grid(row=0, column=1, sticky='ew')
        playback_center_box.grid_columnconfigure(0, weight=1)
        playback_center_box.grid_columnconfigure(1, weight=1)
        playback_center_box.grid_columnconfigure(2, weight=1)

        speed_up_box = tk.LabelFrame(playback_shell, text='Speed', padx=8, pady=8, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        speed_up_box.grid(row=0, column=2, sticky='nse', padx=(8, 0))
        self._make_button(speed_up_box, '> 0.25x', 8, enabled=False).grid(row=0, column=0, sticky='ew')

        self._make_button(playback_center_box, 'Back', 12, enabled=False).grid(row=0, column=0, padx=(0, 4), pady=(0, 8), sticky='ew')
        self._make_button(playback_center_box, 'Play / Pause', 12, enabled=False).grid(row=0, column=1, padx=(0, 4), pady=(0, 8), sticky='ew')
        self._make_button(playback_center_box, 'Skip', 12, enabled=False).grid(row=0, column=2, pady=(0, 8), sticky='ew')

        playback_progress_box = tk.Frame(playback_center_box, bg=PLAYBACK_PANEL_COLOR)
        playback_progress_box.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))
        playback_progress_box.grid_columnconfigure(1, weight=1)

        tk.Label(playback_progress_box, text='3:30', bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=(0, 10))

        playback_progress_canvas = tk.Canvas(
            playback_progress_box,
            width=280,
            height=26,
            bg=PLAYBACK_PANEL_COLOR,
            highlightthickness=0,
            bd=0,
        )
        playback_progress_canvas.grid(row=0, column=1, sticky='ew')
        playback_progress_canvas.create_line(12, 13, 268, 13, fill=BORDER_COLOR, width=4)
        playback_progress_canvas.create_line(12, 13, 140, 13, fill=ACCENT_COLOR, width=4)
        playback_progress_canvas.create_oval(132, 5, 148, 21, fill=BUTTON_COLOR, outline=BUTTON_TEXT_COLOR, width=2)

        tk.Label(playback_progress_box, text='7:42', bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=2, sticky='e', padx=(10, 0))

        self._make_button(future_box, 'Family Friendly', 20, enabled=False).grid(row=3, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'No Requests', 20, enabled=False).grid(row=3, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Subscriber Priority', 20, enabled=False).grid(row=3, column=2, pady=(0, 8), sticky='w')
        self._make_button(future_box, 'All Media', 20, enabled=False).grid(row=4, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Just Videos', 20, enabled=False).grid(row=4, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Just Audio', 20, enabled=False).grid(row=4, column=2, pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Under 5 Minutes Length', 20, enabled=False).grid(row=5, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Under 3 Minutes', 20, enabled=False).grid(row=5, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Under 1 Minute', 20, enabled=False).grid(row=5, column=2, pady=(0, 8), sticky='w')
        tk.Checkbutton(
            future_box,
            text='No Shuffled Duplicates within 24 hours - if song played via shuffle or request, it will not be shuffled to in shuffle mode',
            state='disabled',
            bg=PANEL_COLOR,
            fg=TEXT_COLOR,
            selectcolor=ENTRY_COLOR,
            activebackground=PANEL_COLOR,
            activeforeground=TEXT_COLOR,
            disabledforeground=DISABLED_TEXT_COLOR,
            highlightthickness=0,
            bd=0,
            anchor='w',
        ).grid(row=6, column=0, columnspan=3, sticky='w', pady=(6, 0))

        footer = tk.Label(frame, textvariable=self.status_message, anchor='w', bg=BG_COLOR, fg=TEXT_COLOR)
        footer.pack(fill='x', pady=(14, 0))

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _start_status_loop(self) -> None:
        self._update_status_labels()
        self.root.after(1500, self._start_status_loop)

    def _update_status_labels(self) -> None:
        self.jukebox_status.set(self._service_label(self.jukebox_process, 8765))
        self.visualizer_status.set(self._service_label(self.visualizer_process, 4173))

    def _service_label(self, process: subprocess.Popen[str] | None, port: int) -> str:
        if process and process.poll() is None:
            return f'Running on port {port}'
        if self._port_open(port):
            return f'Running on port {port}'
        return 'Stopped'

    def _port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex(('127.0.0.1', port)) == 0

    def start_bard_system(self) -> None:
        self.start_jukebox()
        self.start_visualizer()
        self.status_message.set('Started Bard system services.')

    def start_and_open_everything(self) -> None:
        self.start_bard_system()

        def delayed_open() -> None:
            self._wait_for_port(8765, timeout_seconds=18)
            self._wait_for_port(4173, timeout_seconds=18)
            self.open_main_pages()

        threading.Thread(target=delayed_open, daemon=True).start()
        self.status_message.set('Starting services and opening pages when ready...')

    def open_main_pages(self) -> None:
        self.open_url(self.jukebox_url.get())
        self.open_url(self.controller_url.get())
        self.status_message.set('Opened jukebox player and visualizer controller.')

    def start_jukebox(self) -> None:
        if self._port_open(8765):
            self.status_message.set('Jukebox already appears to be running.')
            return

        if not JUKEBOX_DIR.exists():
            messagebox.showerror('Missing Jukebox', f'Could not find jukebox folder:\n{JUKEBOX_DIR}')
            return

        self.jukebox_process = self._spawn_process([sys.executable, 'main.py'], JUKEBOX_DIR)
        self.status_message.set('Starting jukebox...')

    def start_visualizer(self) -> None:
        if self._port_open(4173):
            self.status_message.set('Visualizer already appears to be running.')
            return

        if not VISUALIZER_DIR.exists():
            messagebox.showerror('Missing Visualizer', f'Could not find visualizer folder:\n{VISUALIZER_DIR}')
            return

        self.visualizer_process = self._spawn_process(['npm.cmd', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '4173'], VISUALIZER_DIR)
        self.status_message.set('Starting visualizer...')

    def stop_all(self) -> None:
        self._stop_process(self.jukebox_process)
        self._stop_process(self.visualizer_process)
        self.jukebox_process = None
        self.visualizer_process = None
        self.status_message.set('Requested stop for launcher-managed services.')

    def _spawn_process(self, command: list[str], cwd: Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            creationflags=PROCESS_FLAGS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
        )

    def _wait_for_port(self, port: int, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            if self._port_open(port):
                return True
            time.sleep(0.35)

        return False

    def _stop_process(self, process: subprocess.Popen[str] | None) -> None:
        if not process or process.poll() is not None:
            return

        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                return

    def open_url(self, url: str) -> None:
        threading.Thread(target=lambda: webbrowser.open(url, new=2), daemon=True).start()
        self.status_message.set(f'Opened {url}')

    def copy_obs_url(self) -> None:
        self.copy_text(self.obs_url.get(), 'Copied OBS visualizer URL to clipboard.')

    def copy_text(self, value: str, status: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()
        self.status_message.set(status)

    def toggle_urls_visibility(self) -> None:
        self.urls_visible = not self.urls_visible
        self.url_visibility_text.set('Hide All Links' if self.urls_visible else 'Show All Links')
        self._refresh_display_urls()
        self.status_message.set('Updated link visibility in the URL reference section.')

    def _refresh_display_urls(self) -> None:
        hidden_value = '< Hidden >'
        self.display_jukebox_url.set(self.jukebox_url.get() if self.urls_visible else hidden_value)
        self.display_controller_url.set(self.controller_url.get() if self.urls_visible else hidden_value)
        self.display_obs_url.set(self.obs_url.get() if self.urls_visible else hidden_value)

    def _on_close(self) -> None:
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    BardControlCenter(root)
    root.mainloop()


if __name__ == '__main__':
    main()
