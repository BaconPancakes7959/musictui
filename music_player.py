"""
TUI music player - v1
"""

import curses
import os
import random
import socket
import json
import subprocess
import threading
import time
from pathlib import Path
from wcwidth import wcswidth

ACCENT_COLOR = 215

KEY_QUIT           = ord('q')
KEY_SEARCH         = ord('/')
KEY_CLEAR_SEARCH   = ord('c')
KEY_SHUFFLE        = ord('s')
KEY_NEXT_SONG      = ord('n')
KEY_PREV_SONG      = ord('p')
KEY_PLAY_SELECTED  = ord('\n')
KEY_PAUSE          = ord(' ')
KEY_SEEK_FORWARD   = ord('l')
KEY_SEEK_BACKWARD  = ord('j')
KEY_VOL_DOWN       = ord('-')
KEY_VOL_UP_MINUS   = ord('=')
KEY_VOL_UP_PLUS    = ord('+')
KEY_MUTE           = ord('m')
KEY_PAUSE_ALT      = ord('k')
KEY_HELP_TOGGLE    = ord('h')
KEY_REPEAT         = ord('r')


def visual_width(text):
    if not text:
        return 0
    return wcswidth(text)


def truncate_by_visual_width(text, max_width):
    if visual_width(text) <= max_width:
        return text
    for i in range(len(text), 0, -1):
        if visual_width(text[:i]) <= max_width - 3:
            return text[:i] + "..."
    return text[:max_width - 3] + "..." if max_width > 3 else "..."


class MusicBackend:
    def __init__(self):
        self.process = None
        self.current_track_path = None
        self.current_duration = 0
        self.current_position = 0
        self.socket_path = "/tmp/mpv-music-player.sock"
        self.socket = None
        self._position_lock = threading.Lock()
        self._on_track_end = None

        self.volume = 100
        self.muted = False

        self._generation = 0
        self._gen_lock = threading.Lock()

    def _cleanup_socket(self):
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except:
            pass

    def _send_command(self, command):
        if not self.socket:
            return False
        try:
            cmd_json = json.dumps({"command": command}) + "\n"
            self.socket.send(cmd_json.encode())
            return True
        except:
            return False

    def _get_property(self, prop_name):
        if not self.socket:
            return None
        try:
            cmd_json = json.dumps({"command": ["get_property", prop_name], "request_id": 1}) + "\n"
            self.socket.send(cmd_json.encode())
            self.socket.settimeout(0.05)
            data = self.socket.recv(4096)
            response = json.loads(data.decode())
            if "data" in response:
                return response["data"]
        except:
            pass
        return None

    def set_track_end_callback(self, callback):
        self._on_track_end = callback

    def get_duration(self, path):
        try:
            import mutagen.mp3
            audio = mutagen.mp3.MP3(str(path))
            return audio.info.length
        except:
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries",
                       "format=duration", "-of",
                       "default=noprint_wrappers=1:nokey=1", str(path)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                return float(result.stdout.strip())
            except:
                return 0

    def play(self, path):
        with self._gen_lock:
            self._generation += 1
            my_generation = self._generation

        self._async_stop()
        self._cleanup_socket()

        self.current_track_path = str(path)
        with self._position_lock:
            self.current_position = 0
            self.current_duration = 0

        def load_duration():
            duration = self.get_duration(path)
            with self._position_lock:
                self.current_duration = duration
        threading.Thread(target=load_duration, daemon=True).start()

        self.process = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal", "--no-osc",
             f"--volume={self.volume}",
             f"--input-ipc-server={self.socket_path}",
             self.current_track_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(10):
            time.sleep(0.1)
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(self.socket_path)
                self.socket.settimeout(0.05)
                break
            except:
                continue

        if self.muted:
            self._send_command(["set_property", "mute", True])

        def monitor(gen):
            proc = self.process
            if proc:
                proc.wait()
            with self._gen_lock:
                still_current = (gen == self._generation)
            if still_current and self._on_track_end:
                self._on_track_end()

        threading.Thread(target=monitor, args=(my_generation,), daemon=True).start()

    def _async_stop(self):
        """Grab references, clear them, kill in background - never blocks caller."""
        proc = self.process
        sock = self.socket
        self.process = None
        self.socket = None

        def _kill(p, s):
            if s:
                try:
                    s.close()
                except:
                    pass
            if p:
                try:
                    p.terminate()
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
                except:
                    pass

        threading.Thread(target=_kill, args=(proc, sock), daemon=True).start()

    def toggle_pause(self):
        return self._send_command(["cycle", "pause"])

    def seek_forward(self, seconds=10):
        return self._send_command(["seek", seconds, "relative"])

    def seek_backward(self, seconds=10):
        return self._send_command(["seek", -seconds, "relative"])

    def seek_to(self, position):
        return self._send_command(["seek", position, "absolute"])

    def volume_up(self, step=5):
        self.volume = min(130, self.volume + step)
        self._send_command(["set_property", "volume", self.volume])

    def volume_down(self, step=5):
        self.volume = max(0, self.volume - step)
        self._send_command(["set_property", "volume", self.volume])

    def toggle_mute(self):
        self.muted = not self.muted
        self._send_command(["set_property", "mute", self.muted])

    def update_position(self):
        if self.socket and self.current_track_path:
            pos = self._get_property("time-pos")
            if pos is not None:
                with self._position_lock:
                    self.current_position = float(pos)
        with self._position_lock:
            return self.current_position

    def get_position(self):
        with self._position_lock:
            return self.current_position

    def get_duration_safe(self):
        with self._position_lock:
            return self.current_duration

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def stop(self):
        """Synchronous stop - waits for mpv to fully die. Used on quit."""
        with self._gen_lock:
            self._generation += 1 

        proc = self.process
        sock = self.socket
        self.process = None
        self.socket = None

        if sock:
            try:
                cmd_json = json.dumps({"command": ["quit"]}) + "\n"
                sock.send(cmd_json.encode())
                time.sleep(0.05)
            except:
                pass
            try:
                sock.close()
            except:
                pass

        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            except:
                try:
                    proc.kill()
                    proc.wait()
                except:
                    pass

        try:
            subprocess.run(
                ["pkill", "-f", f"mpv.*{self.socket_path}"],
                capture_output=True, timeout=2
            )
        except:
            pass


class Library:
    def __init__(self, music_path):
        self.music_path = Path(music_path).expanduser()
        self.all_songs = []
        self.display_songs = []
        self.search_query = ""
        self.shuffle_mode = False
        self.shuffle_order = []
        self.current_shuffle_index = 0
        self.duration_cache = {}
        self.refresh()

    def refresh(self):
        if not self.music_path.exists():
            self.all_songs = []
            self.display_songs = []
            return
        self.all_songs = list(self.music_path.rglob("*.mp3"))
        self.all_songs.sort()
        self._update_display()

    def _update_display(self):
        if not self.search_query:
            self.display_songs = self.all_songs.copy()
        else:
            query_lower = self.search_query.lower()
            self.display_songs = [
                song for song in self.all_songs
                if query_lower in song.stem.lower()
            ]
        if self.shuffle_mode and self.display_songs:
            self.shuffle_order = list(range(len(self.display_songs)))
            random.shuffle(self.shuffle_order)
            self.current_shuffle_index = 0

    def set_search(self, query):
        self.search_query = query
        self._update_display()

    def clear_search(self):
        self.search_query = ""
        self._update_display()

    def get_song_duration(self, path):
        path_str = str(path)
        if path_str not in self.duration_cache:
            try:
                import mutagen.mp3
                audio = mutagen.mp3.MP3(path_str)
                self.duration_cache[path_str] = audio.info.length
            except:
                self.duration_cache[path_str] = 0
        return self.duration_cache[path_str]

    def toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        if self.shuffle_mode and self.display_songs:
            self.shuffle_order = list(range(len(self.display_songs)))
            random.shuffle(self.shuffle_order)
            self.current_shuffle_index = 0
        else:
            self.shuffle_order = []

    def get_next_track(self, current_track):
        if not self.display_songs:
            return None
        if self.shuffle_mode and self.shuffle_order:
            if current_track:
                current_idx = None
                for i, song in enumerate(self.display_songs):
                    if str(song) == current_track:
                        current_idx = i
                        break
                if current_idx is not None:
                    for pos, idx in enumerate(self.shuffle_order):
                        if idx == current_idx:
                            self.current_shuffle_index = (pos + 1) % len(self.shuffle_order)
                            return self.display_songs[self.shuffle_order[self.current_shuffle_index]]
            return self.display_songs[self.shuffle_order[0]]
        else:
            if current_track:
                for i, song in enumerate(self.display_songs):
                    if str(song) == current_track:
                        return self.display_songs[(i + 1) % len(self.display_songs)]
            return self.display_songs[0] if self.display_songs else None

    def get_previous_track(self, current_track):
        if not self.display_songs:
            return None
        if self.shuffle_mode and self.shuffle_order:
            if current_track:
                current_idx = None
                for i, song in enumerate(self.display_songs):
                    if str(song) == current_track:
                        current_idx = i
                        break
                if current_idx is not None:
                    for pos, idx in enumerate(self.shuffle_order):
                        if idx == current_idx:
                            self.current_shuffle_index = (pos - 1) % len(self.shuffle_order)
                            return self.display_songs[self.shuffle_order[self.current_shuffle_index]]
            return self.display_songs[self.shuffle_order[-1]]
        else:
            if current_track:
                for i, song in enumerate(self.display_songs):
                    if str(song) == current_track:
                        return self.display_songs[(i - 1) % len(self.display_songs)]
            return self.display_songs[0] if self.display_songs else None

    def format_duration(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"


class MusicPlayerUI:
    def __init__(self, stdscr, library, backend):
        self.stdscr = stdscr
        self.library = library
        self.backend = backend
        self.current_selection_idx = 0
        self.search_mode = False
        self.search_input = ""
        self.needs_refresh = True
        self.show_help = False
        self.help_scroll = 0
        self.repeat_mode = False

        self.backend.set_track_end_callback(self.on_track_finished)

        curses.curs_set(0)
        self.setup_colors()

    def setup_colors(self):
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, -1)
            curses.init_pair(2, curses.COLOR_BLACK, ACCENT_COLOR)
            curses.init_pair(3, ACCENT_COLOR, -1)
            curses.init_pair(4, ACCENT_COLOR, -1)

    def on_track_finished(self):
        if self.repeat_mode and self.backend.current_track_path:
            self.backend.play(self.backend.current_track_path)
            self.needs_refresh = True
            return
        next_track = self.library.get_next_track(self.backend.current_track_path)
        if next_track:
            for i, song in enumerate(self.library.display_songs):
                if str(song) == str(next_track):
                    self.current_selection_idx = i
                    break
            self.backend.play(str(next_track))
            self.needs_refresh = True

    def draw(self):
        height, width = self.stdscr.getmaxyx()

        if self.show_help:
            self.draw_help_screen()
            return

        if not hasattr(self, '_last_size') or self._last_size != (height, width):
            self.stdscr.clear()
            self._last_size = (height, width)

        title = "Music Player"
        x = (width - len(title)) // 2
        self.stdscr.attron(curses.A_BOLD | curses.color_pair(4))
        self.stdscr.addstr(0, x, title)
        self.stdscr.attroff(curses.A_BOLD | curses.color_pair(4))

        if self.search_mode:
            search_text = f" Search: {self.search_input}_"
            self.stdscr.attron(curses.A_REVERSE)
            self.stdscr.addstr(1, 0, search_text[:width - 1].ljust(width - 1))
            self.stdscr.attroff(curses.A_REVERSE)
        elif self.library.search_query:
            results_text = f" Results for '{self.library.search_query}' - {len(self.library.display_songs)} songs"
            self.stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
            self.stdscr.addstr(1, 0, results_text[:width - 1].ljust(width - 1))
            self.stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)
        else:
            self.stdscr.addstr(1, 0, " " * (width - 1))

        start_y = 2
        list_bottom = height - 3   
        max_items = list_bottom - start_y

        for clear_y in range(start_y, list_bottom):
            self.stdscr.addstr(clear_y, 0, " " * (width - 1))

        if not self.library.display_songs:
            if self.library.search_query:
                self.stdscr.addstr(start_y, 2, f"No songs found matching '{self.library.search_query}'")
            else:
                self.stdscr.addstr(start_y, 2, "No MP3 files found in ~/Music!")
        else:
            start_idx = max(0, self.current_selection_idx - max_items + 1)
            end_idx = min(len(self.library.display_songs), start_idx + max_items)

            for i, idx in enumerate(range(start_idx, end_idx)):
                y = start_y + i
                if y >= list_bottom:
                    break

                song = self.library.display_songs[idx]
                name = song.stem
                duration = self.library.get_song_duration(song)
                duration_str = self.library.format_duration(duration)

                is_playing = (self.backend.current_track_path == str(song))
                is_selected = (idx == self.current_selection_idx)

                prefix = "  "
                max_name_width = width - len(duration_str) - len(prefix) - 4
                display_name = truncate_by_visual_width(name, max_name_width) if visual_width(name) > max_name_width else name

                line = f"{prefix}{display_name}"
                line_width = visual_width(line)
                spaces_needed = max(1, width - line_width - len(duration_str) - 1)

                self.stdscr.addstr(y, 0, " " * (width - 1))

                if is_selected:
                    self.stdscr.attron(curses.color_pair(2))
                    self.stdscr.addstr(y, 0, line)
                    self.stdscr.addstr(y, line_width, " " * spaces_needed)
                    self.stdscr.addstr(y, line_width + spaces_needed, duration_str)
                    self.stdscr.attroff(curses.color_pair(2))
                elif is_playing:
                    self.stdscr.attron(curses.color_pair(3))
                    self.stdscr.addstr(y, 0, line)
                    self.stdscr.addstr(y, line_width, " " * spaces_needed)
                    self.stdscr.addstr(y, line_width + spaces_needed, duration_str)
                    self.stdscr.attroff(curses.color_pair(3))
                else:
                    self.stdscr.addstr(y, 0, line)
                    self.stdscr.addstr(y, line_width, " " * spaces_needed)
                    self.stdscr.addstr(y, line_width + spaces_needed, duration_str)

        progress_y = height - 2
        self.stdscr.addstr(progress_y, 0, " " * (width - 1))

        if self.backend.current_track_path:
            pos = self.backend.get_position()
            duration = self.backend.get_duration_safe()
            if duration > 0:
                progress = min(1.0, pos / duration)
                bar_width = width - 2
                filled = int(bar_width * progress)
                self.stdscr.attron(curses.color_pair(3))
                self.stdscr.addstr(progress_y, 1, "─" * filled)
                self.stdscr.attroff(curses.color_pair(3))
                self.stdscr.addstr(progress_y, 1 + filled, "─" * (bar_width - filled))

        status_y = height - 1
        self.stdscr.addstr(status_y, 0, " " * (width - 1))

        shuffle_tag = "[S] " if self.library.shuffle_mode else ""
        repeat_tag  = "[R] " if self.repeat_mode else ""
        mute_tag    = "[M] " if self.backend.muted else ""
        vol_tag     = f"Vol:{self.backend.volume}"

        if self.backend.current_track_path:
            left = f"{shuffle_tag}{repeat_tag}{mute_tag}Now Playing: "
            name = Path(self.backend.current_track_path).stem
            duration = self.backend.get_duration_safe()
            if duration > 0:
                pos = self.backend.get_position()
                right = f"{vol_tag}  {self.backend.format_time(pos)} / {self.backend.format_time(duration)}"
            else:
                right = vol_tag
            max_name_w = max(1, width - len(left) - len(right) - 2)
            if visual_width(name) > max_name_w:
                name = truncate_by_visual_width(name, max_name_w)
            left += name
            right_x = width - len(right) - 1
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(status_y, 0, left[:right_x])
            self.stdscr.addstr(status_y, right_x, right)
            self.stdscr.attroff(curses.color_pair(4))
        else:
            left  = f"{shuffle_tag}{repeat_tag}{mute_tag}No Song Playing"
            right = vol_tag
            right_x = width - len(right) - 1
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(status_y, 0, left[:right_x])
            self.stdscr.addstr(status_y, right_x, right)
            self.stdscr.attroff(curses.color_pair(4))

        self.stdscr.refresh()

    def draw_help_screen(self):
        height, width = self.stdscr.getmaxyx()

        current_size = (height, width)
        if not hasattr(self, '_help_last_size') or self._help_last_size != current_size:
            self.stdscr.clear()
            self._help_last_size = current_size

        keybinds = [
            ("Playback", [
                ("Space / k",  "Pause / Resume"),
                ("Enter",      "Play selected song"),
                ("p",          "Previous song"),
                ("n",          "Next song"),
            ]),
            ("Seeking", [
                ("← / →",      "Seek -5 / +5 seconds"),
                ("j / l",      "Seek -10 / +10 seconds"),
                ("0 - 9",      "Jump to 0% - 90% of song"),
            ]),
            ("Volume", [
                ("- / =",      "Volume down / up"),
                ("m",          "Toggle mute"),
            ]),
            ("Navigation", [
                ("↑ / ↓",      "Move selection"),
            ]),
            ("Search", [
                ("/",          "Open search"),
                ("Enter",      "Apply search"),
                ("Esc / c",    "Exit search / clear results"),
            ]),
            ("Other", [
                ("s",          "Toggle shuffle"),
                ("r",          "Toggle repeat"),
                ("h",          "Toggle this help screen"),
                ("q",          "Quit"),
            ]),
        ]

        lines = []
        key_col  = 4
        sep_col  = 22
        desc_col = 25
        for section, binds in keybinds:
            lines.append(("section", section))
            for k, desc in binds:
                lines.append(("bind", (k, desc)))
            lines.append(("blank", ""))

        total_lines = len(lines)
        visible_rows = max(1, height - 4)

        max_scroll = max(0, total_lines - visible_rows)
        self.help_scroll = max(0, min(self.help_scroll, max_scroll))

        title = "Keybinds"
        self.stdscr.attron(curses.A_BOLD | curses.color_pair(4))
        self.stdscr.addstr(0, max(0, (width - len(title)) // 2), title[:width - 1])
        self.stdscr.attroff(curses.A_BOLD | curses.color_pair(4))

        self.stdscr.addstr(1, 0, "─" * (width - 1))

        for screen_row in range(visible_rows):
            line_idx = screen_row + self.help_scroll
            y = screen_row + 2
            if y >= height - 1:
                break
            self.stdscr.addstr(y, 0, " " * (width - 1))
            if line_idx >= total_lines:
                continue
            kind, data = lines[line_idx]
            if kind == "section":
                self.stdscr.attron(curses.A_BOLD)
                self.stdscr.addstr(y, key_col, data[:width - key_col - 1])
                self.stdscr.attroff(curses.A_BOLD)
            elif kind == "bind":
                k, desc = data
                self.stdscr.attron(curses.color_pair(3))
                self.stdscr.addstr(y, key_col, k[:max(0, sep_col - key_col - 1)])
                self.stdscr.attroff(curses.color_pair(3))
                if sep_col < width:
                    self.stdscr.addstr(y, sep_col, "│")
                if desc_col < width:
                    self.stdscr.addstr(y, desc_col, desc[:width - desc_col - 1])

        footer_left = " press h to go back "
        footer_right = f" {int(self.help_scroll / max_scroll * 100)}% ↑↓ to scroll " if max_scroll > 0 else ""
        self.stdscr.addstr(height - 1, 0, " " * (width - 1))
        self.stdscr.attron(curses.color_pair(4))
        lx = max(0, (width - len(footer_left)) // 2)
        self.stdscr.addstr(height - 1, lx, footer_left[:width - lx - 1])
        if footer_right:
            rx = width - len(footer_right) - 1
            if rx > lx + len(footer_left):
                self.stdscr.addstr(height - 1, rx, footer_right[:width - rx - 1])
        self.stdscr.attroff(curses.color_pair(4))

        self.stdscr.refresh()

    def play_song_at_index(self, idx):
        if 0 <= idx < len(self.library.display_songs):
            song = self.library.display_songs[idx]
            self.backend.play(str(song))
            self.current_selection_idx = idx
            self.needs_refresh = True

    def apply_search(self):
        self.library.set_search(self.search_input)
        self.search_mode = False
        self.search_input = ""
        self.current_selection_idx = 0
        curses.curs_set(0)
        self.needs_refresh = True

    def clear_search(self):
        self.library.clear_search()
        self.current_selection_idx = 0
        self.needs_refresh = True

    def run(self):
        self.draw()

        last_position_update = 0

        while True:
            current_time = time.time()

            if current_time - last_position_update > 0.1:
                self.backend.update_position()
                last_position_update = current_time
                self.needs_refresh = True

            if self.needs_refresh:
                self.draw()
                self.needs_refresh = False

            self.stdscr.nodelay(1)
            try:
                key = self.stdscr.getch()
            except:
                key = -1
            finally:
                self.stdscr.nodelay(0)

            if key == -1:
                time.sleep(0.033)
                continue

            if key == curses.KEY_RESIZE:
                self._last_size = None
                self._help_last_size = None
                self.stdscr.clear()
                self.needs_refresh = True
                continue

            if not self.search_mode and not self.show_help and ord('0') <= key <= ord('9'):
                duration = self.backend.get_duration_safe()
                if duration > 0:
                    fraction = (key - ord('0')) / 10.0
                    self.backend.seek_to(duration * fraction)
                    self.needs_refresh = True
                continue

            if self.search_mode:
                if key == ord('\n'):
                    self.apply_search()
                elif key == 27:  # ESC
                    self.search_mode = False
                    self.search_input = ""
                    curses.curs_set(0)
                    self.needs_refresh = True
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    self.search_input = self.search_input[:-1]
                    self.needs_refresh = True
                elif 32 <= key <= 126:
                    self.search_input += chr(key)
                    self.needs_refresh = True
                continue

            if key == KEY_QUIT:
                break
            elif key == KEY_SEARCH:
                self.search_mode = True
                self.search_input = ""
                curses.curs_set(1)
                self.needs_refresh = True
            elif key == KEY_CLEAR_SEARCH:
                self.clear_search()
            elif key == KEY_SHUFFLE:
                self.library.toggle_shuffle()
                self.needs_refresh = True
            elif key == KEY_REPEAT:
                self.repeat_mode = not self.repeat_mode
                self.needs_refresh = True
            elif key == curses.KEY_UP:
                if self.show_help:
                    self.help_scroll = max(0, self.help_scroll - 1)
                    self.needs_refresh = True
                elif self.current_selection_idx > 0:
                    self.current_selection_idx -= 1
                    self.needs_refresh = True
            elif key == curses.KEY_DOWN:
                if self.show_help:
                    self.help_scroll += 1
                    self.needs_refresh = True
                elif self.current_selection_idx < len(self.library.display_songs) - 1:
                    self.current_selection_idx += 1
                    self.needs_refresh = True
            elif key == KEY_NEXT_SONG:
                self.next_song()
            elif key == KEY_PREV_SONG:
                self.previous_song()
            elif key == KEY_PLAY_SELECTED:
                if self.library.display_songs:
                    self.play_song_at_index(self.current_selection_idx)
            elif key == KEY_PAUSE:
                self.backend.toggle_pause()
                self.needs_refresh = True
            elif key == KEY_SEEK_FORWARD:
                self.backend.seek_forward(10)
                self.needs_refresh = True
            elif key == KEY_SEEK_BACKWARD:
                self.backend.seek_backward(10)
                self.needs_refresh = True
            elif key == KEY_VOL_DOWN:
                self.backend.volume_down()
                self.needs_refresh = True
            elif key in (KEY_VOL_UP_MINUS, KEY_VOL_UP_PLUS):
                self.backend.volume_up()
                self.needs_refresh = True
            elif key == KEY_MUTE:
                self.backend.toggle_mute()
                self.needs_refresh = True
            elif key == KEY_PAUSE_ALT:
                self.backend.toggle_pause()
                self.needs_refresh = True
            elif key == KEY_HELP_TOGGLE:
                self.show_help = not self.show_help
                self.help_scroll = 0
                self._help_last_size = None
                self.stdscr.clear()
                self.needs_refresh = True
            elif key == 27:  # ESC - clear search
                self.clear_search()
            elif key == curses.KEY_RIGHT:
                self.backend.seek_forward(5)
                self.needs_refresh = True
            elif key == curses.KEY_LEFT:
                self.backend.seek_backward(5)
                self.needs_refresh = True

    def next_song(self):
        next_track = self.library.get_next_track(self.backend.current_track_path)
        if next_track:
            for i, song in enumerate(self.library.display_songs):
                if str(song) == str(next_track):
                    self.play_song_at_index(i)
                    break
        elif self.library.display_songs:
            self.play_song_at_index(0)

    def previous_song(self):
        prev_track = self.library.get_previous_track(self.backend.current_track_path)
        if prev_track:
            for i, song in enumerate(self.library.display_songs):
                if str(song) == str(prev_track):
                    self.play_song_at_index(i)
                    break
        elif self.library.display_songs:
            self.play_song_at_index(0)

    
def main(stdscr):
    os.environ.setdefault('ESCDELAY', '25')
    curses.set_escdelay(25)
    music_library = Library("~/Music")
    audio_backend = MusicBackend()

    if not music_library.all_songs:
        music_library = Library(".")
        if not music_library.all_songs:
            stdscr.addstr(0, 0, "No MP3 files found!")
            stdscr.refresh()
            stdscr.getch()
            return

    ui = MusicPlayerUI(stdscr, music_library, audio_backend)
    try:
        ui.run()
    finally:
        audio_backend.stop()


if __name__ == "__main__":
    curses.wrapper(main)
