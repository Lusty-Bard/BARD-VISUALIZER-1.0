from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox
from urllib import error, parse, request

ROOT_DIR = Path(__file__).resolve().parent
CASCADE_PROJECTS_DIR = ROOT_DIR.parent
JUKEBOX_DIR = CASCADE_PROJECTS_DIR / 'BARD JUKEBOX 1.0'
VISUALIZER_DIR = ROOT_DIR

JUKEBOX_URL = 'http://127.0.0.1:8765/player'
JUKEBOX_CONTROL_STATE_URL = 'http://127.0.0.1:8765/api/control-state'
JUKEBOX_CONTROL_ACTION_URL = 'http://127.0.0.1:8765/api/control-action'
JUKEBOX_CATALOG_URL = 'http://127.0.0.1:8765/api/catalog'
JUKEBOX_SONG_ROW_URL = 'http://127.0.0.1:8765/api/song-row'
JUKEBOX_SONG_COLUMN_URL = 'http://127.0.0.1:8765/api/song-column'
JUKEBOX_SONG_COLUMN_DELETE_URL = 'http://127.0.0.1:8765/api/song-column-delete'
JUKEBOX_QUEUE_STATE_URL = 'http://127.0.0.1:8765/api/queue-state'
JUKEBOX_QUEUE_ACTION_URL = 'http://127.0.0.1:8765/api/queue-action'
JUKEBOX_RELOAD_LIBRARY_URL = 'http://127.0.0.1:8765/api/reload-library'
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
LEGACY_PANEL_COLOR = '#313137'
LEGACY_TEXT_COLOR = '#a4a4ae'

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
        self.root.geometry('920x760')
        self.root.minsize(820, 520)
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
        self.family_mode_var = tk.BooleanVar(value=False)
        self.requests_enabled_var = tk.BooleanVar(value=True)
        self.best_only_var = tk.BooleanVar(value=False)
        self.no_duplicates_var = tk.BooleanVar(value=False)
        self.playback_left_time = tk.StringVar(value='0:00')
        self.playback_right_time = tk.StringVar(value='0:00')
        self.playback_now_playing = tk.StringVar(value='Nothing playing')
        self.catalog_query = tk.StringVar(value='')
        self.catalog_search_field = tk.StringVar(value='all')
        self.catalog_media_type_filter = tk.StringVar(value='all')
        self.catalog_adult_filter = tk.StringVar(value='all')
        self.catalog_live_filter = tk.StringVar(value='all')
        self.catalog_count_text = tk.StringVar(value='Catalog: unavailable')
        self.songs_csv_path = tk.StringVar(value=str(JUKEBOX_DIR / 'songs.csv'))
        self.catalog_columns_text = tk.StringVar(value='Recommended columns: title, filename, adult, media_type, length_seconds, best')
        self.queue_summary_text = tk.StringVar(value='Queue: unavailable')
        self.catalog_selection_index = tk.StringVar(value='1')
        self.queue_selection_index = tk.StringVar(value='1')
        self.editor_original_title = tk.StringVar(value='')
        self.editor_title = tk.StringVar(value='')
        self.editor_filename = tk.StringVar(value='')
        self.editor_adult = tk.StringVar(value='N')
        self.editor_media_type = tk.StringVar(value='audio')
        self.editor_length_seconds = tk.StringVar(value='')
        self.editor_best = tk.StringVar(value='N')
        self.new_column_name = tk.StringVar(value='')
        self.delete_column_name = tk.StringVar(value='')
        self.playback_volume_text = tk.StringVar(value='Vol 100%')
        self.control_buttons: dict[str, tk.Button] = {}
        self.playback_progress_canvas: tk.Canvas | None = None
        self.playback_volume_scale: tk.Scale | None = None
        self.catalog_search_field_menu: tk.OptionMenu | None = None
        self.last_control_state: dict[str, object] = {}
        self.catalog_text: tk.Text | None = None
        self.queue_text: tk.Text | None = None
        self.last_catalog_rows: list[dict[str, object]] = []
        self.last_queue_rows: list[dict[str, object]] = []
        self.catalog_columns: list[str] = ['title', 'filename', 'adult', 'media_type', 'length_seconds', 'best']
        self.dynamic_editor_fields: dict[str, tk.StringVar] = {}
        self.dynamic_editor_container: tk.Frame | None = None
        self._catalog_row_line_numbers: list[int] = []
        self._seek_dragging = False
        self._playback_progress_width = 280
        self._playback_progress_left = 12
        self._playback_progress_right = self._playback_progress_width - 12
        self._catalog_scroll_fraction = 0.0

        self._build_ui()
        self._refresh_display_urls()
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
            padx=5,
            pady=3,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
            font=('Segoe UI', 9, 'bold'),
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

        frame = tk.Frame(canvas, padx=12, pady=12, bg=BG_COLOR)
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

        title = tk.Label(frame, text='Jukebox Dashboard', font=('Segoe UI', 18, 'bold'), bg=BG_COLOR, fg=ACCENT_COLOR)
        title.pack(anchor='w')

        subtitle = tk.Label(
            frame,
            text='Live playback, song library, queue, and song editing in one dashboard.',
            font=('Segoe UI', 10),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
        )
        subtitle.pack(anchor='w', pady=(4, 16))

        playback_box = tk.LabelFrame(frame, text='Playback Controls', padx=12, pady=10, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        playback_box.pack(fill='x')

        tk.Label(
            playback_box,
            text='Live playback controls and seek for the current jukebox track.',
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
        self.control_buttons['speed_down'] = self._make_button(speed_down_box, '< 0.25x', 8, lambda: self.send_control_action('speed_delta', -0.25))
        self.control_buttons['speed_down'].grid(row=0, column=0, sticky='ew')

        playback_center_box = tk.Frame(playback_shell, bg=PLAYBACK_PANEL_COLOR)
        playback_center_box.grid(row=0, column=1, sticky='ew')
        playback_center_box.grid_columnconfigure(0, weight=1)
        playback_center_box.grid_columnconfigure(1, weight=1)
        playback_center_box.grid_columnconfigure(2, weight=1)

        speed_up_box = tk.LabelFrame(playback_shell, text='Speed', padx=8, pady=8, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        speed_up_box.grid(row=0, column=2, sticky='nse', padx=(8, 0))
        self.control_buttons['speed_up'] = self._make_button(speed_up_box, '> 0.25x', 8, lambda: self.send_control_action('speed_delta', 0.25))
        self.control_buttons['speed_up'].grid(row=0, column=0, sticky='ew')

        self.control_buttons['back'] = self._make_button(playback_center_box, 'Back', 12, lambda: self.send_control_action('back'))
        self.control_buttons['back'].grid(row=0, column=0, padx=(0, 4), pady=(0, 8), sticky='ew')
        self.control_buttons['play_pause'] = self._make_button(playback_center_box, 'Play / Pause', 12, lambda: self.send_control_action('play_pause'))
        self.control_buttons['play_pause'].grid(row=0, column=1, padx=(0, 4), pady=(0, 8), sticky='ew')
        self.control_buttons['skip'] = self._make_button(playback_center_box, 'Skip', 12, lambda: self.send_control_action('skip'))
        self.control_buttons['skip'].grid(row=0, column=2, pady=(0, 8), sticky='ew')

        tk.Label(playback_center_box, textvariable=self.playback_now_playing, justify='left', anchor='w', bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 6))

        playback_progress_box = tk.Frame(playback_center_box, bg=PLAYBACK_PANEL_COLOR)
        playback_progress_box.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(6, 0))
        playback_progress_box.grid_columnconfigure(1, weight=1)

        tk.Label(playback_progress_box, textvariable=self.playback_left_time, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=(0, 10))

        self.playback_progress_canvas = tk.Canvas(
            playback_progress_box,
            width=self._playback_progress_width,
            height=26,
            bg=PLAYBACK_PANEL_COLOR,
            highlightthickness=0,
            bd=0,
            cursor='hand2',
        )
        self.playback_progress_canvas.grid(row=0, column=1, sticky='ew')
        self.playback_progress_canvas.bind('<Button-1>', self._on_progress_press)
        self.playback_progress_canvas.bind('<B1-Motion>', self._on_progress_drag)
        self.playback_progress_canvas.bind('<ButtonRelease-1>', self._on_progress_release)
        self.playback_progress_canvas.bind('<Configure>', self._on_progress_canvas_resize)

        tk.Label(playback_progress_box, textvariable=self.playback_right_time, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=2, sticky='e', padx=(10, 0))

        volume_box = tk.Frame(playback_center_box, bg=PLAYBACK_PANEL_COLOR)
        volume_box.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        volume_box.grid_columnconfigure(1, weight=1)
        tk.Label(volume_box, text='Volume', bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.playback_volume_scale = tk.Scale(
            volume_box,
            from_=0,
            to=130,
            orient='horizontal',
            showvalue=False,
            resolution=1,
            bg=PLAYBACK_PANEL_COLOR,
            fg=TEXT_COLOR,
            highlightthickness=0,
            troughcolor=ENTRY_COLOR,
            activebackground=ACCENT_COLOR,
            command=self._on_volume_scale_changed,
        )
        self.playback_volume_scale.grid(row=0, column=1, sticky='ew')
        self.playback_volume_scale.set(100)
        tk.Label(volume_box, textvariable=self.playback_volume_text, bg=PLAYBACK_PANEL_COLOR, fg=TEXT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=2, sticky='e', padx=(10, 0))

        self._redraw_playback_progress(0.0, 0.0)

        quick_box = tk.LabelFrame(frame, text='Quick Start', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        self._make_button(quick_box, 'Start Bard System', 22, self.start_bard_system).grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Start + Open Everything', 22, self.start_and_open_everything).grid(row=0, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Open Controller + Player', 22, self.open_main_pages).grid(row=0, column=2, pady=(0, 8), sticky='w')
        self._make_button(quick_box, 'Stop All', 22, self.stop_all).grid(row=1, column=0, padx=(0, 10), sticky='w')
        self._make_button(quick_box, 'Copy OBS URL', 22, self.copy_obs_url).grid(row=1, column=1, padx=(0, 10), sticky='w')
        self._make_button(quick_box, 'Open OBS Visualizer URL', 22, lambda: self.open_url(self.obs_url.get())).grid(row=1, column=2, sticky='w')

        status_box = tk.LabelFrame(frame, text='Status', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        tk.Label(status_box, text='Jukebox:', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=0, column=0, sticky='w')
        tk.Label(status_box, textvariable=self.jukebox_status, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=0, column=1, sticky='w', padx=(8, 0))
        tk.Label(status_box, text='Visualizer:', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=1, column=0, sticky='w', pady=(6, 0))
        tk.Label(status_box, textvariable=self.visualizer_status, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(6, 0))

        launch_box = tk.LabelFrame(frame, text='Services', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        self._make_button(launch_box, 'Start Jukebox', 24, self.start_jukebox).grid(row=1, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(launch_box, 'Start Visualizer', 24, self.start_visualizer).grid(row=1, column=1, pady=(0, 8), sticky='w')

        links_box = tk.LabelFrame(frame, text='Open Pages', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        self._make_button(links_box, 'Open Jukebox Player', 24, lambda: self.open_url(self.jukebox_url.get())).grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(links_box, 'Open Visualizer Controller', 24, lambda: self.open_url(self.controller_url.get())).grid(row=0, column=1, pady=(0, 8), sticky='w')
        self._make_button(links_box, 'Open Jukebox + Controller', 24, self.open_main_pages).grid(row=1, column=0, padx=(0, 10), sticky='w')
        self._make_button(links_box, 'Open OBS Visualizer URL', 24, lambda: self.open_url(self.obs_url.get())).grid(row=1, column=1, sticky='w')

        urls_box = tk.LabelFrame(frame, text='URLs', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        toggle_links_button = self._make_button(urls_box, '', 10, self.toggle_urls_visibility)
        toggle_links_button.configure(textvariable=self.url_visibility_text)
        toggle_links_button.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))

        tk.Label(urls_box, text='Jukebox Player', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=1, column=0, sticky='w')
        tk.Entry(urls_box, textvariable=self.display_jukebox_url, width=72, bg=ENTRY_COLOR, fg=LEGACY_TEXT_COLOR, insertbackground=LEGACY_TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=1, column=1, padx=(10, 10), sticky='we')
        self._make_button(urls_box, 'Copy', 10, lambda: self.copy_text(self.jukebox_url.get(), 'Copied jukebox player URL.')).grid(row=1, column=3, sticky='e')

        tk.Label(urls_box, text='Visualizer Controller', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=2, column=0, sticky='w', pady=(8, 0))
        tk.Entry(urls_box, textvariable=self.display_controller_url, width=72, bg=ENTRY_COLOR, fg=LEGACY_TEXT_COLOR, insertbackground=LEGACY_TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=2, column=1, padx=(10, 10), pady=(8, 0), sticky='we')
        self._make_button(urls_box, 'Copy', 10, lambda: self.copy_text(self.controller_url.get(), 'Copied controller URL.')).grid(row=2, column=3, pady=(8, 0), sticky='e')

        tk.Label(urls_box, text='OBS Visualizer', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).grid(row=3, column=0, sticky='w', pady=(8, 0))
        tk.Entry(urls_box, textvariable=self.display_obs_url, width=72, bg=ENTRY_COLOR, fg=LEGACY_TEXT_COLOR, insertbackground=LEGACY_TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=3, column=1, padx=(10, 10), pady=(8, 0), sticky='we')
        self._make_button(urls_box, 'Copy', 10, self.copy_obs_url).grid(row=3, column=3, pady=(8, 0), sticky='e')

        urls_box.grid_columnconfigure(1, weight=1)

        notes_box = tk.LabelFrame(frame, text='Notes', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        notes = (
            'Current easy flow:\n'
            '1. Click Start + Open Everything\n'
            '2. In the controller tab, click Connect audio\n'
            '3. In OBS, use the OBS Visualizer URL as a Browser Source\n'
            '4. Keep the controller tab available while streaming\n\n'
            'If the visualizer only updates while its tab is active, that is usually browser throttling.\n'
            'For now, keep the controller tab visible during use. A more robust future fix would move capture/control into a desktop wrapper.'
        )
        tk.Label(notes_box, text=notes, justify='left', anchor='w', bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR).pack(fill='both', expand=True)

        future_box = tk.LabelFrame(frame, text='Under Construction / Legacy Controls', padx=12, pady=10, bg=LEGACY_PANEL_COLOR, fg=LEGACY_TEXT_COLOR, bd=2, relief='solid')

        tk.Label(
            future_box,
            text='Older launcher and extra control sections live below. Some are active, but this area is still being reorganized and polished.',
            justify='left',
            anchor='w',
            bg=LEGACY_PANEL_COLOR,
            fg=LEGACY_TEXT_COLOR,
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        self.control_buttons['family_friendly'] = self._make_button(future_box, 'Family Friendly', 20, lambda: self.send_control_action('family_mode'))
        self.control_buttons['family_friendly'].grid(row=3, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self.control_buttons['no_requests'] = self._make_button(future_box, 'No Requests', 20, lambda: self.send_control_action('requests_enabled'))
        self.control_buttons['no_requests'].grid(row=3, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self._make_button(future_box, 'Subscriber Priority', 20, enabled=False).grid(row=3, column=2, pady=(0, 8), sticky='w')
        self.control_buttons['all_media'] = self._make_button(future_box, 'All Media', 20, lambda: self.send_control_action('media_mode', 'all'))
        self.control_buttons['all_media'].grid(row=4, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self.control_buttons['just_videos'] = self._make_button(future_box, 'Just Videos', 20, lambda: self.send_control_action('media_mode', 'video'))
        self.control_buttons['just_videos'].grid(row=4, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self.control_buttons['just_audio'] = self._make_button(future_box, 'Just Audio', 20, lambda: self.send_control_action('media_mode', 'audio'))
        self.control_buttons['just_audio'].grid(row=4, column=2, pady=(0, 8), sticky='w')
        self.control_buttons['under_5'] = self._make_button(future_box, 'Under 5 Minutes Length', 20, lambda: self.send_control_action('max_length_seconds', 300))
        self.control_buttons['under_5'].grid(row=5, column=0, padx=(0, 10), pady=(0, 8), sticky='w')
        self.control_buttons['under_3'] = self._make_button(future_box, 'Under 3 Minutes', 20, lambda: self.send_control_action('max_length_seconds', 180))
        self.control_buttons['under_3'].grid(row=5, column=1, padx=(0, 10), pady=(0, 8), sticky='w')
        self.control_buttons['under_1'] = self._make_button(future_box, 'Under 1 Minute', 20, lambda: self.send_control_action('max_length_seconds', 60))
        self.control_buttons['under_1'].grid(row=5, column=2, pady=(0, 8), sticky='w')
        tk.Checkbutton(
            future_box,
            text='No Shuffled Duplicates within 24 hours - if song played via shuffle or request, it will not be shuffled to in shuffle mode',
            variable=self.no_duplicates_var,
            command=lambda: self.send_control_action('no_shuffle_duplicates_24h', self.no_duplicates_var.get()),
            bg=LEGACY_PANEL_COLOR,
            fg=LEGACY_TEXT_COLOR,
            selectcolor=ENTRY_COLOR,
            activebackground=LEGACY_PANEL_COLOR,
            activeforeground=LEGACY_TEXT_COLOR,
            highlightthickness=0,
            bd=0,
            anchor='w',
        ).grid(row=6, column=0, columnspan=3, sticky='w', pady=(6, 0))

        library_box = tk.LabelFrame(frame, text='Song Library Browser', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        library_box.pack(fill='both', expand=True, pady=(14, 0))
        library_box.grid_columnconfigure(1, weight=1)
        library_box.grid_rowconfigure(5, weight=1)

        tk.Label(library_box, text='Search', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, sticky='w')
        search_entry = tk.Entry(
            library_box,
            textvariable=self.catalog_query,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
        )
        search_entry.grid(row=0, column=1, sticky='ew', padx=(8, 10))
        search_entry.bind('<Return>', lambda _event: self.refresh_catalog())
        self._make_button(library_box, 'Refresh List', 14, self.refresh_catalog).grid(row=0, column=2, sticky='e', padx=(0, 8))
        self._make_button(library_box, 'Reload songs.csv', 14, self.reload_library).grid(row=0, column=3, sticky='e')
        self._make_button(library_box, 'Add Search Top Result', 18, self.queue_first_catalog_result).grid(row=0, column=4, sticky='e', padx=(8, 8))
        self._make_button(library_box, 'Add Selected Result', 18, self.queue_selected_catalog_result).grid(row=0, column=5, sticky='e')

        tk.Label(library_box, text='Field', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.catalog_search_field_menu = tk.OptionMenu(library_box, self.catalog_search_field, 'all', *self.catalog_columns)
        self.catalog_search_field_menu.configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR, highlightthickness=0, bd=1)
        self.catalog_search_field_menu['menu'].configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR)
        self.catalog_search_field_menu.grid(row=1, column=1, sticky='ew', padx=(8, 10), pady=(8, 0))

        tk.Label(library_box, text='Type', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=2, sticky='w', pady=(8, 0))
        media_type_menu = tk.OptionMenu(library_box, self.catalog_media_type_filter, 'all', 'audio', 'video')
        media_type_menu.configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR, highlightthickness=0, bd=1)
        media_type_menu['menu'].configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR)
        media_type_menu.grid(row=1, column=3, sticky='ew', padx=(8, 10), pady=(8, 0))

        tk.Label(library_box, text='Adult', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=4, sticky='w', pady=(8, 0))
        adult_menu = tk.OptionMenu(library_box, self.catalog_adult_filter, 'all', 'N', 'Y')
        adult_menu.configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR, highlightthickness=0, bd=1)
        adult_menu['menu'].configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR)
        adult_menu.grid(row=1, column=5, sticky='ew', pady=(8, 0))

        tk.Label(library_box, text='Live', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, sticky='w', pady=(8, 0))
        live_menu = tk.OptionMenu(library_box, self.catalog_live_filter, 'all', 'live', 'hidden')
        live_menu.configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR, highlightthickness=0, bd=1)
        live_menu['menu'].configure(bg=ENTRY_COLOR, fg=TEXT_COLOR, activebackground=ACCENT_COLOR, activeforeground=BUTTON_TEXT_COLOR)
        live_menu.grid(row=2, column=1, sticky='ew', padx=(8, 10), pady=(8, 0))
        self._make_button(library_box, 'Apply Filters', 14, self.refresh_catalog).grid(row=2, column=2, sticky='w', padx=(0, 8), pady=(8, 0))

        tk.Label(library_box, textvariable=self.catalog_count_text, bg=PANEL_COLOR, fg=ACCENT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=3, column=0, columnspan=6, sticky='w', pady=(8, 0))
        tk.Label(library_box, text='Selected result #', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=4, column=0, sticky='w', pady=(8, 8))
        tk.Entry(
            library_box,
            textvariable=self.catalog_selection_index,
            width=8,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
        ).grid(row=4, column=1, sticky='w', padx=(8, 10), pady=(8, 8))
        self._make_button(library_box, 'Prev Result', 14, lambda: self._step_selection(self.catalog_selection_index, -1)).grid(row=4, column=2, sticky='w', padx=(0, 8), pady=(8, 8))
        self._make_button(library_box, 'Next Result', 14, lambda: self._step_selection(self.catalog_selection_index, 1)).grid(row=4, column=3, sticky='w', padx=(0, 8), pady=(8, 8))
        self._make_button(library_box, 'Queue Selected', 14, self.queue_selected_catalog_result).grid(row=4, column=4, sticky='e', padx=(0, 8), pady=(8, 8))
        self._make_button(library_box, 'Queue Top', 14, self.queue_first_catalog_result).grid(row=4, column=5, sticky='e', pady=(8, 8))
        tk.Label(library_box, text='songs.csv', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=5, column=0, sticky='w', pady=(8, 8))
        tk.Entry(
            library_box,
            textvariable=self.songs_csv_path,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
        ).grid(row=5, column=1, columnspan=4, sticky='ew', padx=(8, 10), pady=(8, 8))
        self._make_button(library_box, 'Copy Path', 14, lambda: self.copy_text(self.songs_csv_path.get(), 'Copied songs.csv path.')).grid(row=5, column=5, sticky='e', pady=(8, 8))

        catalog_text_frame = tk.Frame(library_box, bg=PANEL_COLOR)
        catalog_text_frame.grid(row=6, column=0, columnspan=6, sticky='nsew')
        catalog_text_frame.grid_columnconfigure(0, weight=1)
        catalog_text_frame.grid_rowconfigure(0, weight=1)
        catalog_scroll = tk.Scrollbar(catalog_text_frame, orient='vertical')
        catalog_scroll.grid(row=0, column=1, sticky='ns')
        self.catalog_text = tk.Text(
            catalog_text_frame,
            height=14,
            wrap='none',
            yscrollcommand=catalog_scroll.set,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
            font=('Consolas', 9),
        )
        self.catalog_text.grid(row=0, column=0, sticky='nsew')
        self.catalog_text.bind('<Button-1>', self._on_catalog_text_click)
        catalog_scroll.configure(command=self.catalog_text.yview)

        queue_box = tk.LabelFrame(frame, text='Upcoming Queue', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        queue_box.pack(fill='both', expand=True, pady=(14, 0))
        queue_box.grid_columnconfigure(0, weight=1)
        queue_box.grid_rowconfigure(1, weight=1)

        queue_header = tk.Frame(queue_box, bg=PANEL_COLOR)
        queue_header.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        queue_header.grid_columnconfigure(0, weight=1)
        tk.Label(queue_header, textvariable=self.queue_summary_text, bg=PANEL_COLOR, fg=ACCENT_COLOR, font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self._make_button(queue_header, 'Refresh Queue', 14, self.refresh_queue).grid(row=0, column=1, sticky='e', padx=(8, 8))
        tk.Label(queue_header, text='Selected queue #', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=2, sticky='e', padx=(0, 6))
        tk.Entry(
            queue_header,
            textvariable=self.queue_selection_index,
            width=8,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
        ).grid(row=0, column=3, sticky='e', padx=(0, 8))
        self._make_button(queue_header, 'Up', 8, lambda: self.move_selected_queue_item(-1)).grid(row=0, column=4, sticky='e', padx=(0, 8))
        self._make_button(queue_header, 'Down', 8, lambda: self.move_selected_queue_item(1)).grid(row=0, column=5, sticky='e', padx=(0, 8))
        self._make_button(queue_header, 'Remove', 10, self.remove_selected_queue_item).grid(row=0, column=6, sticky='e', padx=(0, 8))
        self._make_button(queue_header, 'Clear Queue', 14, lambda: self.send_queue_action('clear')).grid(row=0, column=7, sticky='e')

        queue_text_frame = tk.Frame(queue_box, bg=PANEL_COLOR)
        queue_text_frame.grid(row=1, column=0, sticky='nsew')
        queue_text_frame.grid_columnconfigure(0, weight=1)
        queue_text_frame.grid_rowconfigure(0, weight=1)
        queue_scroll = tk.Scrollbar(queue_text_frame, orient='vertical')
        queue_scroll.grid(row=0, column=1, sticky='ns')
        self.queue_text = tk.Text(
            queue_text_frame,
            height=10,
            wrap='none',
            yscrollcommand=queue_scroll.set,
            bg=ENTRY_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief='solid',
            bd=2,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_COLOR,
            font=('Consolas', 9),
        )
        self.queue_text.grid(row=0, column=0, sticky='nsew')
        self.queue_text.bind('<Button-1>', self._on_queue_text_click)
        queue_scroll.configure(command=self.queue_text.yview)

        editor_box = tk.LabelFrame(frame, text='Selected Song Editor', padx=12, pady=10, bg=PANEL_COLOR, fg=TEXT_COLOR, bd=2, relief='solid')
        editor_box.pack(fill='x', pady=(14, 0))
        editor_box.grid_columnconfigure(1, weight=1)
        editor_box.grid_columnconfigure(3, weight=1)

        tk.Label(editor_box, text='Original title', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_original_title, state='readonly', readonlybackground=ENTRY_COLOR, fg=TEXT_COLOR, bg=ENTRY_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=0, column=1, columnspan=3, sticky='ew', padx=(8, 10), pady=(0, 8))

        tk.Label(editor_box, text='Title', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_title, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=1, column=1, sticky='ew', padx=(8, 10), pady=(0, 8))
        tk.Label(editor_box, text='Filename', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=1, column=2, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_filename, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=1, column=3, sticky='ew', padx=(8, 0), pady=(0, 8))

        tk.Label(editor_box, text='Adult', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_adult, width=8, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=2, column=1, sticky='w', padx=(8, 10), pady=(0, 8))
        tk.Label(editor_box, text='Media type', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=2, column=2, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_media_type, width=12, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=2, column=3, sticky='w', padx=(8, 0), pady=(0, 8))

        tk.Label(editor_box, text='Length', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=3, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_length_seconds, width=12, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=3, column=1, sticky='w', padx=(8, 10), pady=(0, 8))
        tk.Label(editor_box, text='Best', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=3, column=2, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.editor_best, width=8, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=3, column=3, sticky='w', padx=(8, 0), pady=(0, 8))

        tk.Label(editor_box, text='New field / column', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=4, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.new_column_name, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=4, column=1, sticky='ew', padx=(8, 10), pady=(0, 8))
        self._make_button(editor_box, '+ Add Field', 14, self.add_song_column).grid(row=4, column=3, sticky='e', pady=(0, 8))

        tk.Label(editor_box, text='Delete field / column', bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=5, column=0, sticky='w', pady=(0, 8))
        tk.Entry(editor_box, textvariable=self.delete_column_name, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=5, column=1, sticky='ew', padx=(8, 10), pady=(0, 8))
        self._make_button(editor_box, 'Delete Field', 14, self.delete_song_column).grid(row=5, column=3, sticky='e', pady=(0, 8))

        self.dynamic_editor_container = tk.Frame(editor_box, bg=PANEL_COLOR)
        self.dynamic_editor_container.grid(row=6, column=0, columnspan=4, sticky='ew', pady=(4, 8))
        self.dynamic_editor_container.grid_columnconfigure(1, weight=1)

        editor_buttons = tk.Frame(editor_box, bg=PANEL_COLOR)
        editor_buttons.grid(row=7, column=0, columnspan=4, sticky='e')
        self._make_button(editor_buttons, 'Load Selected Song', 16, self.load_selected_song_into_editor).grid(row=0, column=0, padx=(0, 8))
        self._make_button(editor_buttons, 'Save Song Changes', 16, self.save_song_editor).grid(row=0, column=1)

        footer = tk.Label(frame, textvariable=self.status_message, anchor='w', bg=BG_COLOR, fg=TEXT_COLOR)
        footer.pack(fill='x', pady=(10, 0))

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _start_status_loop(self) -> None:
        self._update_status_labels()
        self._poll_control_state_async()
        self._poll_catalog_async()
        self._poll_queue_async()
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

    def refresh_catalog(self) -> None:
        self._poll_catalog_async(force=True)

    def refresh_queue(self) -> None:
        self._poll_queue_async(force=True)

    def queue_first_catalog_result(self) -> None:
        if not self.last_catalog_rows:
            self.status_message.set('No catalog result available to queue.')
            return
        top = self.last_catalog_rows[0]
        title = str(top.get('title', '') or '').strip()
        if not title:
            self.status_message.set('Top catalog result has no title.')
            return
        self.send_queue_action('add_by_title', title)

    def queue_selected_catalog_result(self) -> None:
        if not self.last_catalog_rows:
            self.status_message.set('No catalog result available to queue.')
            return
        index = self._selection_index(self.catalog_selection_index.get(), len(self.last_catalog_rows))
        if index is None:
            self.status_message.set('Selected result number is out of range.')
            return
        row = self.last_catalog_rows[index]
        title = str(row.get('title', '') or '').strip()
        if not title:
            self.status_message.set('Selected catalog result has no title.')
            return
        self.send_queue_action('add_by_title', title)

    def load_selected_song_into_editor(self) -> None:
        if not self.last_catalog_rows:
            self.status_message.set('No catalog result available to edit.')
            return
        index = self._selection_index(self.catalog_selection_index.get(), len(self.last_catalog_rows))
        if index is None:
            self.status_message.set('Selected result number is out of range.')
            return
        row = self.last_catalog_rows[index]
        title = str(row.get('title', '') or '').strip()
        if not title:
            self.status_message.set('Selected catalog result has no title.')
            return
        self._fetch_song_row(title)

    def save_song_editor(self) -> None:
        original_title = self.editor_original_title.get().strip()
        if not original_title:
            self.status_message.set('Load a song into the editor before saving.')
            return
        updates = {
            'title': self.editor_title.get().strip(),
            'filename': self.editor_filename.get().strip(),
            'adult': self.editor_adult.get().strip(),
            'media_type': self.editor_media_type.get().strip(),
            'length_seconds': self.editor_length_seconds.get().strip(),
            'best': self.editor_best.get().strip(),
        }
        for name, variable in self.dynamic_editor_fields.items():
            updates[name] = variable.get().strip()
        self._save_song_row(original_title, updates)

    def add_song_column(self) -> None:
        column_name = self.new_column_name.get().strip()
        if not column_name:
            self.status_message.set('Enter a field / column name first.')
            return
        self._create_song_column(column_name)

    def delete_song_column(self) -> None:
        column_name = self.delete_column_name.get().strip()
        if not column_name:
            self.status_message.set('Enter a field / column name to delete.')
            return
        confirmed = messagebox.askyesno('Delete Field', f'Delete the field "{column_name}" from songs.csv for every song? This cannot be undone automatically.')
        if not confirmed:
            return
        self._delete_song_column(column_name)

    def remove_selected_queue_item(self) -> None:
        index = self._selection_index(self.queue_selection_index.get(), len(self.last_queue_rows))
        if index is None:
            self.status_message.set('Selected queue number is invalid.')
            return
        self.send_queue_action('remove_at', index)

    def move_selected_queue_item(self, direction: int) -> None:
        index = self._selection_index(self.queue_selection_index.get(), len(self.last_queue_rows))
        if index is None:
            self.status_message.set('Selected queue number is invalid.')
            return
        target_index = index + (-1 if direction < 0 else 1)
        if target_index < 0 or target_index >= len(self.last_queue_rows):
            self.status_message.set('Selected queue item cannot move further in that direction.')
            return
        self.queue_selection_index.set(str(target_index + 1))
        self.send_queue_action('move_up' if direction < 0 else 'move_down', index)
        self._apply_row_highlight(self.queue_text, self.queue_selection_index, len(self.last_queue_rows))

    def reload_library(self) -> None:
        if not self._port_open(8765):
            self.status_message.set('Reload requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                response = self._post_json(JUKEBOX_RELOAD_LIBRARY_URL, {})
                count = int(response.get('count', 0)) if isinstance(response, dict) else 0
                self.root.after(0, lambda: self.status_message.set(f'Reloaded songs.csv. Catalog rows: {count}'))
                self.root.after(0, self.refresh_catalog)
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Reload failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _delete_song_column(self, column_name: str) -> None:
        if not self._port_open(8765):
            self.status_message.set('Song editor requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                response = self._post_json(JUKEBOX_SONG_COLUMN_DELETE_URL, {'name': column_name})
                columns = response.get('columns') if isinstance(response, dict) else None
                if isinstance(columns, list):
                    names = [str(col.get('name', '')) for col in columns if isinstance(col, dict) and col.get('name')]
                    self.root.after(0, lambda: self._set_catalog_columns(names))
                self.root.after(0, lambda: self.delete_column_name.set(''))
                self.root.after(0, lambda: self.status_message.set(f'Deleted field: {column_name}'))
                self.root.after(0, self.refresh_catalog)
                current_title = self.editor_original_title.get().strip()
                if current_title:
                    self.root.after(0, lambda: self._fetch_song_row(current_title))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Delete field failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _send_seek_ratio(self, ratio: float) -> None:
        self.send_control_action('seek_ratio', max(0.0, min(1.0, ratio)))

    def _fetch_song_row(self, title: str) -> None:
        if not self._port_open(8765):
            self.status_message.set('Song editor requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                qs = parse.urlencode({'title': title})
                response = self._get_json(f'{JUKEBOX_SONG_ROW_URL}?{qs}')
                row = response.get('row') if isinstance(response, dict) else None
                if isinstance(row, dict):
                    self.root.after(0, lambda: self._apply_song_editor_row(row))
                    self.root.after(0, lambda: self.status_message.set(f'Loaded editor row: {title}'))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Could not load song editor row: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_song_editor_row(self, row: dict[str, object]) -> None:
        self.editor_original_title.set(str(row.get('title', '') or ''))
        self.editor_title.set(str(row.get('title', '') or ''))
        self.editor_filename.set(str(row.get('filename', '') or ''))
        self.editor_adult.set(str(row.get('adult', 'N') or 'N'))
        self.editor_media_type.set(str(row.get('media_type', '') or ''))
        self.editor_length_seconds.set(str(row.get('length_seconds', '') or ''))
        self.editor_best.set(str(row.get('best', 'N') or 'N'))
        self._render_dynamic_editor_fields(row)

    def _save_song_row(self, original_title: str, updates: dict[str, str]) -> None:
        if not self._port_open(8765):
            self.status_message.set('Song editor requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                response = self._post_json(JUKEBOX_SONG_ROW_URL, {'original_title': original_title, 'updates': updates})
                row = response.get('row') if isinstance(response, dict) else None
                if isinstance(row, dict):
                    self.root.after(0, lambda: self._apply_song_editor_row(row))
                self.root.after(0, self.refresh_catalog)
                self.root.after(0, lambda: self.status_message.set(f'Saved song row: {updates.get("title", original_title)}'))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Save song row failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _create_song_column(self, column_name: str) -> None:
        if not self._port_open(8765):
            self.status_message.set('Song editor requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                response = self._post_json(JUKEBOX_SONG_COLUMN_URL, {'name': column_name})
                columns = response.get('columns') if isinstance(response, dict) else None
                if isinstance(columns, list):
                    names = [str(col.get('name', '')) for col in columns if isinstance(col, dict) and col.get('name')]
                    self.root.after(0, lambda: self._set_catalog_columns(names))
                self.root.after(0, lambda: self.new_column_name.set(''))
                self.root.after(0, lambda: self.status_message.set(f'Added field: {column_name}'))
                self.root.after(0, self.refresh_catalog)
                current_title = self.editor_original_title.get().strip()
                if current_title:
                    self.root.after(0, lambda: self._fetch_song_row(current_title))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Add field failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _set_catalog_columns(self, names: list[str]) -> None:
        if names:
            self.catalog_columns = names
            self.catalog_columns_text.set('Recommended columns: ' + ', '.join(names))
            self._refresh_catalog_search_field_menu()
            if self.catalog_search_field.get() not in {'all', *names}:
                self.catalog_search_field.set('all')

    def _refresh_catalog_search_field_menu(self) -> None:
        if self.catalog_search_field_menu is None:
            return
        menu = self.catalog_search_field_menu['menu']
        menu.delete(0, 'end')
        choices = ['all', *self.catalog_columns]
        for choice in choices:
            menu.add_command(label=choice, command=tk._setit(self.catalog_search_field, choice))

    def _render_dynamic_editor_fields(self, row: dict[str, object]) -> None:
        if self.dynamic_editor_container is None:
            return
        for child in self.dynamic_editor_container.winfo_children():
            child.destroy()
        core_fields = {'jukebox_id', 'title', 'filename', 'adult', 'media_type', 'length_seconds', 'best', 'length_display'}
        dynamic_names = [name for name in self.catalog_columns if name and name not in core_fields]
        self.dynamic_editor_fields = {}
        if not dynamic_names:
            tk.Label(self.dynamic_editor_container, text='No extra fields yet. Add one with + Add Field.', bg=PANEL_COLOR, fg=LEGACY_TEXT_COLOR, anchor='w', justify='left').grid(row=0, column=0, columnspan=2, sticky='w')
            return
        for index, name in enumerate(dynamic_names):
            variable = tk.StringVar(value=str(row.get(name, '') or ''))
            self.dynamic_editor_fields[name] = variable
            tk.Label(self.dynamic_editor_container, text=name, bg=PANEL_COLOR, fg=TEXT_COLOR).grid(row=index, column=0, sticky='w', pady=(0, 6), padx=(0, 8))
            tk.Entry(self.dynamic_editor_container, textvariable=variable, bg=ENTRY_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief='solid', bd=2, highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_COLOR).grid(row=index, column=1, sticky='ew', pady=(0, 6))

    def send_queue_action(self, action: str, value: object | None = None) -> None:
        if not self._port_open(8765):
            self.status_message.set('Queue controls require the jukebox service to be running.')
            return

        def worker() -> None:
            payload: dict[str, object] = {'action': action}
            if value is not None:
                payload['value'] = value
            try:
                response = self._post_json(JUKEBOX_QUEUE_ACTION_URL, payload)
                self.root.after(0, lambda: self._apply_queue_response(response))
                self.root.after(0, lambda: self.status_message.set(f'Sent queue action: {action}'))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Queue action failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def send_control_action(self, action: str, value: object | None = None) -> None:
        if not self._port_open(8765):
            self.status_message.set('Jukebox controls require the jukebox service to be running.')
            return

        def worker() -> None:
            payload: dict[str, object] = {'action': action}
            if value is not None:
                payload['value'] = value
            try:
                response = self._post_json(JUKEBOX_CONTROL_ACTION_URL, payload)
                control_state = response.get('control_state') if isinstance(response, dict) else None
                if isinstance(control_state, dict):
                    self.root.after(0, lambda: self._apply_control_state(control_state))
                self.root.after(0, lambda: self.status_message.set(f'Sent control action: {action}'))
            except Exception as exc:
                self.root.after(0, lambda: self.status_message.set(f'Control action failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_catalog_async(self, force: bool = False) -> None:
        if not self._port_open(8765):
            if force:
                self.status_message.set('Song catalog requires the jukebox service to be running.')
            return

        query = self.catalog_query.get().strip()
        search_field = self.catalog_search_field.get().strip() or 'all'
        media_type = self.catalog_media_type_filter.get().strip() or 'all'
        adult = self.catalog_adult_filter.get().strip() or 'all'
        live = self.catalog_live_filter.get().strip() or 'all'

        def worker() -> None:
            try:
                qs = parse.urlencode({
                    'q': query,
                    'search_field': search_field,
                    'media_type': media_type,
                    'adult': adult,
                    'live': live,
                    'limit': 500,
                })
                response = self._get_json(f'{JUKEBOX_CATALOG_URL}?{qs}')
                self.root.after(0, lambda: self._apply_catalog_response(response))
            except Exception as exc:
                if force:
                    self.root.after(0, lambda: self.status_message.set(f'Catalog refresh failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_catalog_response(self, response: dict[str, object]) -> None:
        rows = response.get('rows') if isinstance(response, dict) else []
        if not isinstance(rows, list):
            rows = []
        count = int(response.get('count', len(rows))) if isinstance(response, dict) else len(rows)
        total_catalog_count = int(response.get('total_catalog_count', count)) if isinstance(response, dict) else count
        visible_filtered_count = int(response.get('visible_filtered_count', count)) if isinstance(response, dict) else count
        songs_csv_path = str(response.get('songs_csv_path', self.songs_csv_path.get())) if isinstance(response, dict) else self.songs_csv_path.get()
        columns = response.get('columns') if isinstance(response, dict) else []
        active_search_field = str(response.get('search_field', self.catalog_search_field.get())) if isinstance(response, dict) else self.catalog_search_field.get()
        active_media_type = str(response.get('media_type', self.catalog_media_type_filter.get())) if isinstance(response, dict) else self.catalog_media_type_filter.get()
        active_adult = str(response.get('adult', self.catalog_adult_filter.get())) if isinstance(response, dict) else self.catalog_adult_filter.get()
        active_live = str(response.get('live', self.catalog_live_filter.get())) if isinstance(response, dict) else self.catalog_live_filter.get()

        self.last_catalog_rows = [row for row in rows if isinstance(row, dict)]
        self.songs_csv_path.set(songs_csv_path)
        if isinstance(columns, list) and columns:
            self.catalog_columns = [str(col.get('name', '')) for col in columns if isinstance(col, dict) and col.get('name')]
            self.catalog_columns_text.set('Recommended columns: ' + ', '.join(str(col.get('name', '')) for col in columns if isinstance(col, dict) and col.get('name')))
            self._refresh_catalog_search_field_menu()
        self.catalog_search_field.set(active_search_field if active_search_field in {'all', *self.catalog_columns} else 'all')
        self.catalog_media_type_filter.set(active_media_type if active_media_type in {'all', 'audio', 'video'} else 'all')
        self.catalog_adult_filter.set(active_adult if active_adult in {'all', 'N', 'Y'} else 'all')
        self.catalog_live_filter.set(active_live if active_live in {'all', 'live', 'hidden'} else 'all')
        filter_bits: list[str] = []
        if query := self.catalog_query.get().strip():
            filter_bits.append(f'query="{query}"')
        if self.catalog_search_field.get() != 'all':
            filter_bits.append(f'field={self.catalog_search_field.get()}')
        if self.catalog_media_type_filter.get() != 'all':
            filter_bits.append(f'type={self.catalog_media_type_filter.get()}')
        if self.catalog_adult_filter.get() != 'all':
            filter_bits.append(f'adult={self.catalog_adult_filter.get()}')
        if self.catalog_live_filter.get() != 'all':
            filter_bits.append(f'live={self.catalog_live_filter.get()}')
        filter_suffix = f" | Active filters: {', '.join(filter_bits)}" if filter_bits else ''
        self.catalog_count_text.set(f'Search results: {count} / {total_catalog_count} total songs | {visible_filtered_count} currently pass active filters{filter_suffix}')
        self._render_catalog_rows(rows)

    def _render_catalog_rows(self, rows: list[object]) -> None:
        if self.catalog_text is None:
            return
        previous_yview = self.catalog_text.yview()[0] if self.catalog_text.winfo_exists() else self._catalog_scroll_fraction
        dynamic_columns = [name for name in self.catalog_columns if name not in {'jukebox_id', 'title', 'filename', 'adult', 'media_type', 'length_seconds', 'best'}]
        header = f"{'#':>2}  {'JID':6}  {'TITLE':28}  {'TYPE':5}  {'ADULT':5}  {'BEST':4}  {'LEN':8}  {'LIVE':4}  FILENAME\n"
        divider = '-' * 132 + '\n'
        lines = [header, divider]
        line_number = 3
        self._catalog_row_line_numbers = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            self._catalog_row_line_numbers.append(line_number)
            jukebox_id = str(row.get('jukebox_id', ''))[:6]
            title = str(row.get('title', ''))[:31]
            media_type = str(row.get('media_type', ''))[:5]
            adult = str(row.get('adult', ''))[:5]
            best = str(row.get('best', ''))[:4]
            length_display = str(row.get('length_display', ''))[:8]
            live = 'yes' if bool(row.get('matches_current_filters', False)) else 'no'
            filename = str(row.get('filename', ''))
            line = f'{index + 1:>2}  {jukebox_id:6}  {title:28}  {media_type:5}  {adult:5}  {best:4}  {length_display:8}  {live:4}  {filename}'
            lines.append(line + '\n')
            line_number += 1
            if dynamic_columns:
                extras = ' | '.join(
                    f'{name}={str(row.get(name, "") or "")}'
                    for name in dynamic_columns
                    if str(row.get(name, '') or '').strip()
                )
                if extras:
                    lines.append(f'    -> {extras}\n')
                    line_number += 1
        if len(lines) == 2:
            lines.append('No songs matched the current search.\n')
        self.catalog_text.configure(state='normal')
        self.catalog_text.delete('1.0', 'end')
        self.catalog_text.insert('1.0', ''.join(lines))
        self._configure_clickable_text_tags(self.catalog_text)
        self._apply_row_highlight(self.catalog_text, self.catalog_selection_index, len(self.last_catalog_rows))
        self.catalog_text.yview_moveto(previous_yview)
        self._catalog_scroll_fraction = previous_yview
        self.catalog_text.configure(state='disabled')

    def _poll_queue_async(self, force: bool = False) -> None:
        if not self._port_open(8765):
            if force:
                self.status_message.set('Queue view requires the jukebox service to be running.')
            return

        def worker() -> None:
            try:
                response = self._get_json(JUKEBOX_QUEUE_STATE_URL)
                self.root.after(0, lambda: self._apply_queue_response(response))
            except Exception as exc:
                if force:
                    self.root.after(0, lambda: self.status_message.set(f'Queue refresh failed: {exc}'))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_queue_response(self, response: dict[str, object]) -> None:
        now_playing = response.get('now_playing') if isinstance(response, dict) else None
        queue = response.get('queue') if isinstance(response, dict) else []
        queue_length = int(response.get('queue_length', len(queue))) if isinstance(response, dict) else len(queue)
        now_title = ''
        if isinstance(now_playing, dict):
            now_title = str(now_playing.get('title', '') or '')
        summary = f'Queue items: {queue_length}'
        if now_title:
            summary += f' | Now playing: {now_title}'
        self.queue_summary_text.set(summary)
        self.last_queue_rows = [row for row in queue if isinstance(row, dict)] if isinstance(queue, list) else []
        self._render_queue_rows(queue if isinstance(queue, list) else [])

    def _render_queue_rows(self, rows: list[object]) -> None:
        if self.queue_text is None:
            return
        header = f"{'#':>2}  {'TITLE':34}  {'REQUESTED BY':14}  ACTIONS\n"
        divider = '-' * 100 + '\n'
        lines = [header, divider]
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            title = str(row.get('title', ''))[:34]
            requested_by = str(row.get('requested_by', ''))[:14]
            actions = 'remove'
            if index > 0:
                actions = 'up/down/remove'
            elif len(rows) > 1:
                actions = 'down/remove'
            lines.append(f'{index + 1:>2}  {title:34}  {requested_by:14}  {actions}\n')
        if len(lines) == 2:
            lines.append('Queue is currently empty.\n')
        self.queue_text.configure(state='normal')
        self.queue_text.delete('1.0', 'end')
        self.queue_text.insert('1.0', ''.join(lines))
        self._configure_clickable_text_tags(self.queue_text)
        self._apply_row_highlight(self.queue_text, self.queue_selection_index, len(self.last_queue_rows))
        self.queue_text.configure(state='disabled')

    def _on_catalog_text_click(self, event: tk.Event[tk.Text]) -> str:
        if self.catalog_text is None:
            return 'break'
        row_index = self._click_row_index(self.catalog_text, event, len(self.last_catalog_rows))
        if row_index is None:
            return 'break'
        self.catalog_selection_index.set(str(row_index + 1))
        self._apply_row_highlight(self.catalog_text, self.catalog_selection_index, len(self.last_catalog_rows))
        title = str(self.last_catalog_rows[row_index].get('title', '') or '')
        if title:
            self._fetch_song_row(title)
            self.status_message.set(f'Selected catalog row {row_index + 1}: {title}')
        return 'break'

    def _on_queue_text_click(self, event: tk.Event[tk.Text]) -> str:
        if self.queue_text is None:
            return 'break'
        row_index = self._click_row_index(self.queue_text, event, len(self.last_queue_rows))
        if row_index is None:
            return 'break'
        self.queue_selection_index.set(str(row_index + 1))
        self._apply_row_highlight(self.queue_text, self.queue_selection_index, len(self.last_queue_rows))
        title = str(self.last_queue_rows[row_index].get('title', '') or '')
        if title:
            self._fetch_song_row(title)
            self.status_message.set(f'Selected queue row {row_index + 1}: {title}')
        return 'break'

    def _click_row_index(self, widget: tk.Text, event: tk.Event[tk.Text], row_count: int) -> int | None:
        line_number = int(str(widget.index(f'@{event.x},{event.y}')).split('.')[0])
        if widget is self.catalog_text and self._catalog_row_line_numbers:
            selected_index: int | None = None
            for index, start_line in enumerate(self._catalog_row_line_numbers):
                if line_number < start_line:
                    break
                selected_index = index
            if selected_index is None or selected_index >= row_count:
                return None
            return selected_index
        row_index = line_number - 3
        if row_index < 0 or row_index >= row_count:
            return None
        return row_index

    def _configure_clickable_text_tags(self, widget: tk.Text) -> None:
        widget.tag_configure('selected_row', background=ACCENT_COLOR, foreground=BUTTON_TEXT_COLOR)
        widget.tag_remove('selected_row', '1.0', 'end')

    def _apply_row_highlight(self, widget: tk.Text | None, selection_var: tk.StringVar, row_count: int) -> None:
        if widget is None:
            return
        widget.tag_remove('selected_row', '1.0', 'end')
        row_index = self._selection_index(selection_var.get(), row_count)
        if row_index is None:
            return
        if widget is self.catalog_text and row_index < len(self._catalog_row_line_numbers):
            line_number = self._catalog_row_line_numbers[row_index]
        else:
            line_number = row_index + 3
        widget.tag_add('selected_row', f'{line_number}.0', f'{line_number}.end')

    @staticmethod
    def _selection_index(raw_value: str, max_length: int | None) -> int | None:
        try:
            selected = int(str(raw_value).strip())
        except (TypeError, ValueError):
            return None
        index = selected - 1
        if index < 0:
            return None
        if max_length is not None and index >= max_length:
            return None
        return index

    def _step_selection(self, variable: tk.StringVar, delta: int) -> None:
        current = self._selection_index(variable.get(), None)
        if current is None:
            current = 0
        variable.set(str(max(1, current + 1 + delta)))
        if variable is self.catalog_selection_index:
            self._apply_row_highlight(self.catalog_text, self.catalog_selection_index, len(self.last_catalog_rows))
        elif variable is self.queue_selection_index:
            self._apply_row_highlight(self.queue_text, self.queue_selection_index, len(self.last_queue_rows))

    def _poll_control_state_async(self) -> None:
        if not self._port_open(8765):
            return

        def worker() -> None:
            try:
                response = self._get_json(JUKEBOX_CONTROL_STATE_URL)
                control_state = response.get('control_state') if isinstance(response, dict) else None
                if isinstance(control_state, dict):
                    self.root.after(0, lambda: self._apply_control_state(control_state))
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

    def _apply_control_state(self, state: dict[str, object]) -> None:
        self.last_control_state = state
        family_mode = bool(state.get('family_friendly_mode', False))
        requests_enabled = bool(state.get('requests_enabled', True))
        best_only = bool(state.get('best_only', False))
        no_duplicates = bool(state.get('no_shuffle_duplicates_24h', False))
        media_mode = str(state.get('media_mode', 'all'))
        max_length_seconds = state.get('max_length_seconds')
        playback_position = self._safe_float(state.get('playback_position', 0.0))
        playback_duration = self._safe_float(state.get('playback_duration', 0.0))
        now_playing_title = str(state.get('now_playing_title', '') or '')
        now_playing_requested_by = str(state.get('now_playing_requested_by', '') or '')
        playback_paused = bool(state.get('playback_paused', False))
        playback_rate = self._safe_float(state.get('playback_rate', 1.0), 1.0)
        playback_volume = self._safe_float(state.get('playback_volume', 1.0), 1.0)
        last_error = str(state.get('last_error', '') or '')

        self.family_mode_var.set(family_mode)
        self.requests_enabled_var.set(requests_enabled)
        self.best_only_var.set(best_only)
        self.no_duplicates_var.set(no_duplicates)

        title = now_playing_title if now_playing_title else 'Nothing playing'
        if now_playing_requested_by:
            title = f'{title} — {now_playing_requested_by}'
        self.playback_now_playing.set(title)
        self.playback_left_time.set(self._format_time(playback_position))
        self.playback_right_time.set(self._format_time(playback_duration))
        self.playback_volume_text.set(f'Vol {int(max(0.0, min(1.3, playback_volume)) * 100)}%')
        if self.playback_volume_scale is not None:
            desired = int(max(0.0, min(1.3, playback_volume)) * 100)
            if int(float(self.playback_volume_scale.get())) != desired:
                self.playback_volume_scale.set(desired)
        if not self._seek_dragging:
            self._redraw_playback_progress(playback_position, playback_duration)

        self._set_button_active('adult_on', not family_mode)
        self._set_button_active('adult_off', family_mode)
        self._set_button_active('family_friendly', family_mode)
        self._set_button_active('no_requests', not requests_enabled)
        self._set_button_active('best_only', best_only)
        self._set_button_active('all_media', media_mode == 'all')
        self._set_button_active('just_videos', media_mode == 'video')
        self._set_button_active('just_audio', media_mode == 'audio')
        self._set_button_active('only_music', media_mode == 'audio')
        self._set_button_active('only_clips', media_mode == 'video')
        self._set_button_active('no_clips', media_mode == 'audio')
        self._set_button_active('under_5', max_length_seconds == 300)
        self._set_button_active('under_3', max_length_seconds == 180)
        self._set_button_active('under_1', max_length_seconds == 60)

        play_label = f"{'Play' if playback_paused else 'Pause'} / {playback_rate:.2f}x"
        self.control_buttons['play_pause'].configure(text=play_label)
        if last_error:
            self.status_message.set(last_error)

    def _set_button_active(self, name: str, active: bool) -> None:
        button = self.control_buttons.get(name)
        if button is None:
            return
        button.configure(relief='sunken' if active else 'solid', highlightbackground=ACCENT_COLOR if active else BORDER_COLOR)

    def _redraw_playback_progress(self, position: float, duration: float) -> None:
        if self.playback_progress_canvas is None:
            return
        canvas = self.playback_progress_canvas
        canvas.delete('all')
        width = max(self._playback_progress_width, canvas.winfo_width(), 120)
        self._playback_progress_width = width
        left = self._playback_progress_left
        right = self._playback_progress_right
        center_y = 13
        canvas.create_line(left, center_y, right, center_y, fill=BORDER_COLOR, width=4)
        ratio = 0.0 if duration <= 0 else max(0.0, min(1.0, position / duration))
        play_x = left + (right - left) * ratio
        canvas.create_line(left, center_y, play_x, center_y, fill=ACCENT_COLOR, width=4)
        canvas.create_oval(play_x - 8, 5, play_x + 8, 21, fill=BUTTON_COLOR, outline=BUTTON_TEXT_COLOR, width=2)

    def _on_progress_press(self, event: tk.Event[tk.Canvas]) -> str:
        self._seek_dragging = True
        self._apply_seek_from_canvas_x(event.x)
        return 'break'

    def _on_progress_drag(self, event: tk.Event[tk.Canvas]) -> str:
        if not self._seek_dragging:
            return 'break'
        self._apply_seek_from_canvas_x(event.x)
        return 'break'

    def _on_progress_release(self, event: tk.Event[tk.Canvas]) -> str:
        if self._seek_dragging:
            self._apply_seek_from_canvas_x(event.x)
        self._seek_dragging = False
        return 'break'

    def _on_progress_canvas_resize(self, event: tk.Event[tk.Canvas]) -> None:
        self._playback_progress_width = max(120, int(event.width))
        self._playback_progress_right = self._playback_progress_width - self._playback_progress_left
        if not self._seek_dragging:
            position = self._safe_float(self.last_control_state.get('playback_position', 0.0))
            duration = self._safe_float(self.last_control_state.get('playback_duration', 0.0))
            self._redraw_playback_progress(position, duration)

    def _on_volume_scale_changed(self, value: str) -> None:
        try:
            ratio = max(0.0, min(1.3, float(value) / 100.0))
        except ValueError:
            return
        self.playback_volume_text.set(f'Vol {int(ratio * 100)}%')
        current = self._safe_float(self.last_control_state.get('playback_volume', 1.0), 1.0)
        if abs(current - ratio) < 0.01:
            return
        self.send_control_action('volume_set', ratio)

    def _apply_seek_from_canvas_x(self, x: int) -> None:
        duration = self._safe_float(self.last_control_state.get('playback_duration', 0.0))
        if duration <= 0:
            self.status_message.set('Cannot seek until media duration is known.')
            return
        ratio = self._progress_ratio_from_x(x)
        position = duration * ratio
        self.playback_left_time.set(self._format_time(position))
        self._redraw_playback_progress(position, duration)
        self._send_seek_ratio(ratio)
        self.status_message.set(f'Seeking to {int(ratio * 100)}%')

    def _progress_ratio_from_x(self, x: int) -> float:
        self._playback_progress_right = self._playback_progress_width - self._playback_progress_left
        span = max(1, self._playback_progress_right - self._playback_progress_left)
        clamped_x = max(self._playback_progress_left, min(self._playback_progress_right, x))
        return (clamped_x - self._playback_progress_left) / span

    def _get_json(self, url: str) -> dict[str, object]:
        req = request.Request(url, headers={'Accept': 'application/json'})
        with request.urlopen(req, timeout=2.5) as response:
            return json.loads(response.read().decode('utf-8'))

    def _post_json(self, url: str, payload: dict[str, object]) -> dict[str, object]:
        data = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
        with request.urlopen(req, timeout=3.0) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_time(total_seconds: float) -> str:
        whole = max(0, int(total_seconds))
        minutes, seconds = divmod(whole, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f'{hours}:{minutes:02d}:{seconds:02d}'
        return f'{minutes}:{seconds:02d}'

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
