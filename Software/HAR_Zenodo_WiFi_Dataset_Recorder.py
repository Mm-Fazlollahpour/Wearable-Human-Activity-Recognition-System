"""
ESP32 MPU6050 Wi-Fi personal dataset recorder.

Output format is exactly:
    time,label,ax,ay,az,gx,gy,gz

The current Wi-Fi Arduino sketch sends:
    ax,ay,az in g
    gx,gy,gz in deg/s

This recorder converts them to the dataset units:
    ax,ay,az in m/s^2
    gx,gy,gz in rad/s

Timestamp is Unix epoch time in milliseconds, generated as close as possible
to the reception of each TCP line on the laptop.
"""

from __future__ import annotations

import csv
import os
import queue
import re
import socket
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np


DEFAULT_HOST = "192.168.4.1"
DEFAULT_PORT = 3333
GRAVITY_MS2 = 9.80665

DATASET_UNITS = "Dataset: m/s² + rad/s"
ESP32_G_UNITS = "ESP32: g + deg/s"

CSV_HEADER = ["time", "label", "ax", "ay", "az", "gx", "gy", "gz"]


def is_float_text(value: str) -> bool:
    """Same finite-number validation used by the Serial Live program."""
    try:
        number = float(value.strip())
        return bool(np.isfinite(number))
    except (TypeError, ValueError):
        return False


def split_line(line: str) -> list[str]:
    clean = line.strip().replace("\ufeff", "")
    return [part for part in re.split(r"[,;\t ]+", clean) if part]


def parse_stream_line(line: str) -> list[float] | None:
    """Accept the same six/eight-column numeric formats as Serial Live."""
    parts = split_line(line)

    # Current Wi-Fi format: ax,ay,az,gx,gy,gz
    if len(parts) == 6 and all(is_float_text(item) for item in parts):
        return [float(item) for item in parts]

    if len(parts) == 8:
        # Old Arduino format: time,ax,ay,az,temp,gx,gy,gz
        if all(is_float_text(item) for item in parts):
            return [float(parts[index]) for index in (1, 2, 3, 5, 6, 7)]

        # Raw dataset format: time,label,ax,ay,az,gx,gy,gz
        if (
            is_float_text(parts[0])
            and all(is_float_text(parts[index]) for index in (2, 3, 4, 5, 6, 7))
        ):
            return [float(parts[index]) for index in (2, 3, 4, 5, 6, 7)]

    # Header/status/error lines are ignored.
    return None


def convert_to_dataset_units(row: list[float], units_label: str) -> np.ndarray:
    values = np.asarray(row, dtype=np.float32)

    if units_label == ESP32_G_UNITS:
        values = values.copy()
        values[0:3] *= np.float32(GRAVITY_MS2)       # g -> m/s²
        values[3:6] *= np.float32(np.pi / 180.0)     # deg/s -> rad/s

    return values


def format_number(value: float) -> str:
    """Compact decimal output similar to the supplied CSV file."""
    return f"{float(value):.7f}".rstrip("0").rstrip(".")


class WiFiReader(threading.Thread):
    """Receive complete TCP lines without blocking the Tkinter GUI."""

    def __init__(
        self,
        sock: socket.socket,
        sample_queue: queue.Queue,
        status_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.sock = sock
        self.sample_queue = sample_queue
        self.status_queue = status_queue
        self.stop_event = stop_event

    def run(self) -> None:
        buffer = b""

        try:
            while not self.stop_event.is_set():
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    continue

                if not chunk:
                    self.status_queue.put("ESP32 connection closed.")
                    break

                buffer += chunk

                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.decode("ascii", errors="ignore").strip()

                    if not line:
                        continue

                    row = parse_stream_line(line)
                    if row is not None:
                        # Use the timestamp from the laptop at line reception.
                        timestamp_ms = time.time_ns() // 1_000_000
                        self.sample_queue.put((timestamp_ms, row))
                    elif "ERROR" in line.upper():
                        self.status_queue.put(line)

        except OSError as exc:
            if not self.stop_event.is_set():
                self.status_queue.put(f"Socket error: {exc}")
        finally:
            self.status_queue.put("__DISCONNECTED__")


class DatasetRecorderGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ESP32 MPU6050 - Personal Dataset Recorder")
        self.root.geometry("820x560")
        self.root.minsize(720, 480)

        self.sock: socket.socket | None = None
        self.reader: WiFiReader | None = None
        self.stop_event: threading.Event | None = None
        self.sample_queue: queue.Queue = queue.Queue()
        self.status_queue: queue.Queue = queue.Queue()

        self.csv_file = None
        self.csv_writer = None
        self.recording = False
        self.active_label = ""
        self.recorded_count = 0
        self.record_start_monotonic = 0.0
        self.last_rows = deque(maxlen=8)

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.units_var = tk.StringVar(value=ESP32_G_UNITS)
        self.label_var = tk.StringVar(value="Wa")
        self.file_var = tk.StringVar(
            value=str(Path(__file__).with_name("personal_dataset.csv"))
        )
        self.status_var = tk.StringVar(value="برای شروع، اطلاعات فعالیت و فایل را مشخص کنید.")
        self.count_var = tk.StringVar(value="Recorded samples: 0")
        self.time_var = tk.StringVar(value="Recording time: 0.0 s")
        self.last_var = tk.StringVar(value="Last sample: ---")

        self.build_ui()
        self.root.after(30, self.poll_queues)
        self.root.after(200, self.update_recording_time)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self) -> None:
        pad = {"padx": 7, "pady": 7}

        connection = ttk.LabelFrame(self.root, text="Wi-Fi TCP")
        connection.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(connection, text="ESP32 IP:").grid(row=0, column=0, **pad)
        ttk.Entry(connection, textvariable=self.host_var, width=17).grid(row=0, column=1, **pad)
        ttk.Label(connection, text="Port:").grid(row=0, column=2, **pad)
        ttk.Entry(connection, textvariable=self.port_var, width=8).grid(row=0, column=3, **pad)
        ttk.Label(connection, text="Input units:").grid(row=0, column=4, **pad)
        ttk.Combobox(
            connection,
            textvariable=self.units_var,
            values=(ESP32_G_UNITS, DATASET_UNITS),
            state="readonly",
            width=24,
        ).grid(row=0, column=5, **pad)

        settings = ttk.LabelFrame(self.root, text="Dataset settings")
        settings.pack(fill="x", padx=10, pady=5)

        ttk.Label(settings, text="Label:").grid(row=0, column=0, **pad)
        ttk.Combobox(
            settings,
            textvariable=self.label_var,
            values=("C", "D", "J", "T", "U", "Wa", "Wr"),
            width=12,
        ).grid(row=0, column=1, **pad)
        ttk.Label(settings, text="CSV file:").grid(row=0, column=2, **pad)
        ttk.Entry(settings, textvariable=self.file_var, width=48).grid(
            row=0, column=3, columnspan=2, sticky="ew", **pad
        )
        settings.columnconfigure(3, weight=1)

        controls = ttk.LabelFrame(self.root, text="Recording control")
        controls.pack(fill="x", padx=10, pady=5)

        self.start_button = ttk.Button(
            controls,
            text="شروع ضبط",
            command=self.start_recording,
        )
        self.start_button.pack(side="left", padx=15, pady=12, ipadx=25, ipady=8)

        self.stop_button = ttk.Button(
            controls,
            text="پایان ضبط",
            command=self.stop_recording,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=15, pady=12, ipadx=25, ipady=8)

        summary = ttk.LabelFrame(self.root, text="Current recording")
        summary.pack(fill="x", padx=10, pady=5)
        ttk.Label(summary, textvariable=self.count_var, font=("Segoe UI", 12)).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        ttk.Label(summary, textvariable=self.time_var, font=("Segoe UI", 11)).pack(
            anchor="w", padx=12, pady=2
        )
        ttk.Label(summary, textvariable=self.last_var, font=("Consolas", 9)).pack(
            anchor="w", padx=12, pady=(2, 10)
        )

        ttk.Label(
            self.root,
            text=(
                "CSV format: time,label,ax,ay,az,gx,gy,gz | "
                "timestamp = Unix milliseconds | output units = m/s² + rad/s"
            ),
            foreground="#555555",
        ).pack(anchor="w", padx=12, pady=8)

        ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w",
            padding=6,
        ).pack(fill="x", side="bottom")

    def open_csv(self) -> None:
        path = Path(os.path.expandvars(os.path.expanduser(self.file_var.get().strip())))
        if not path.is_absolute():
            path = Path.cwd() / path

        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")

        path.parent.mkdir(parents=True, exist_ok=True)
        is_empty = not path.exists() or path.stat().st_size == 0

        self.csv_file = path.open("a", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file, lineterminator="\r\n")

        if is_empty:
            self.csv_writer.writerow(CSV_HEADER)
            self.csv_file.flush()

        self.file_var.set(str(path))

    def connect_socket(self) -> None:
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            raise ValueError("TCP port must be between 1 and 65535.")

        self.sock = socket.create_connection((host, port), timeout=5.0)
        self.sock.settimeout(1.0)
        self.stop_event = threading.Event()
        self.reader = WiFiReader(
            sock=self.sock,
            sample_queue=self.sample_queue,
            status_queue=self.status_queue,
            stop_event=self.stop_event,
        )
        self.reader.start()

    def start_recording(self) -> None:
        if self.recording:
            return

        label = self.label_var.get().strip()
        if not label:
            messagebox.showerror("Label", "برای فعالیت یک label وارد کنید؛ مثلاً Wa یا J.")
            return

        try:
            # Do not carry samples from a previous stopped connection into
            # the new activity segment.
            while True:
                self.sample_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            self.open_csv()
            self.active_label = label
            self.recorded_count = 0
            self.last_rows.clear()
            self.record_start_monotonic = time.monotonic()
            self.recording = True
            self.connect_socket()
        except Exception as exc:
            self.recording = False
            self.close_csv()
            self.close_socket()
            messagebox.showerror(
                "Start recording",
                f"اتصال به ESP32 یا بازکردن فایل انجام نشد:\n{exc}",
            )
            return

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.count_var.set("Recorded samples: 0")
        self.time_var.set("Recording time: 0.0 s")
        self.status_var.set(
            f"ضبط فعالیت {label} شروع شد؛ داده‌ها در {self.file_var.get()} ذخیره می‌شوند."
        )

    def stop_recording(self) -> None:
        if not self.recording:
            return

        self.recording = False
        count = self.recorded_count
        elapsed = time.monotonic() - self.record_start_monotonic
        self.close_socket()
        self.close_csv()

        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set(
            f"ضبط فعالیت {self.active_label} پایان یافت: "
            f"{count} نمونه در {elapsed:.2f} ثانیه ذخیره شد."
        )

    def close_csv(self) -> None:
        if self.csv_file is not None:
            try:
                self.csv_file.flush()
                self.csv_file.close()
            except OSError:
                pass
        self.csv_file = None
        self.csv_writer = None

    def close_socket(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()

        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass

        self.sock = None
        self.reader = None
        self.stop_event = None

    def save_sample(self, timestamp_ms: int, row: list[float]) -> None:
        if not self.recording or self.csv_writer is None or self.csv_file is None:
            return

        converted = convert_to_dataset_units(row, self.units_var.get())
        output_row = [
            int(timestamp_ms),
            self.active_label,
            *[format_number(value) for value in converted],
        ]
        self.csv_writer.writerow(output_row)
        self.csv_file.flush()

        self.recorded_count += 1
        self.last_rows.append(output_row)
        self.count_var.set(f"Recorded samples: {self.recorded_count}")
        self.last_var.set(
            "Last: " + ",".join(str(value) for value in output_row)
        )

    def poll_queues(self) -> None:
        processed = 0

        while processed < 500:
            try:
                timestamp_ms, row = self.sample_queue.get_nowait()
            except queue.Empty:
                break

            self.save_sample(timestamp_ms, row)
            processed += 1

        while True:
            try:
                message = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if message == "__DISCONNECTED__":
                if self.recording:
                    self.recording = False
                    self.close_csv()
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set("ارتباط ESP32 قطع شد؛ ضبط متوقف شد.")
            else:
                self.status_var.set(message)

        self.root.after(30, self.poll_queues)

    def update_recording_time(self) -> None:
        if self.recording:
            elapsed = time.monotonic() - self.record_start_monotonic
            self.time_var.set(f"Recording time: {elapsed:.1f} s")
        self.root.after(200, self.update_recording_time)

    def on_close(self) -> None:
        if self.recording:
            self.stop_recording()
        else:
            self.close_socket()
            self.close_csv()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass

    DatasetRecorderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
