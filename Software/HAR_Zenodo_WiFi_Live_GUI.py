"""
ESP32 MPU6050 Wi-Fi Live HAR tester.

The ESP32 must run esp32_mpu6050_wifi_server.ino and create:
    SSID: ESP32-MPU6050
    IP:   192.168.4.1
    TCP:  3333

    The current model contract is:
    20 Hz, 40 samples per window, 6 features,
    prediction step = 30 samples (overlap = 10 samples).

    The ESP32 sends the same input format as the working Serial "g mode":
    ax,ay,az in g and gx,gy,gz in deg/s.
    Before prediction, this program converts g + deg/s to the dataset units
    m/s^2 + rad/s, exactly like the Serial Live program.
"""

import os
import re
import queue
import socket
import threading
from collections import deque
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import tensorflow as tf


CLASS_NAMES = [
    "Cycling",
    "Downstairs",
    "Jogging",
    "Typing",
    "Upstairs",
    "Walking",
    "Writing",
]

WINDOW_SIZE = 40
OVERLAP = 10
STEP_SIZE = WINDOW_SIZE - OVERLAP
SAMPLE_RATE_HZ = 20.0
DEFAULT_HOST = "192.168.4.1"
DEFAULT_PORT = 3333
FEATURE_COUNT = 6

# The labels and conversion direction intentionally match the Serial Live file.
DATASET_UNITS = "Dataset: m/s² + rad/s"
ESP32_G_UNITS = "ESP32: g + deg/s"
GRAVITY_MS2 = 9.80665


def is_float_text(value: str) -> bool:
    """Return True only for finite numeric fields."""
    try:
        number = float(value.strip())
        return bool(np.isfinite(number))
    except (TypeError, ValueError):
        return False


def split_line(line: str) -> list[str]:
    clean = line.strip().replace("\ufeff", "")
    return [part for part in re.split(r"[,;\t ]+", clean) if part]


def parse_stream_line(line: str) -> list[float] | None:
    """Use the same numeric checking and formats as the Serial Live program."""
    parts = split_line(line)

    # Current ESP32 Wi-Fi format: ax,ay,az,gx,gy,gz
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

    # Headers and ESP32 diagnostic messages are ignored.
    return None


def convert_units(row: list[float], units_label: str) -> np.ndarray:
    """Convert input units to the exact dataset units used by the model."""
    values = np.asarray(row, dtype=np.float32)

    if units_label == ESP32_G_UNITS:
        values = values.copy()
        values[0:3] *= np.float32(GRAVITY_MS2)          # g -> m/s²
        values[3:6] *= np.float32(np.pi / 180.0)        # deg/s -> rad/s

    return values


def class_label(index: int, output_count: int) -> str:
    if output_count == len(CLASS_NAMES) and 0 <= index < len(CLASS_NAMES):
        return CLASS_NAMES[index]
    return f"Class {index}"


class WiFiLiveHARApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ESP32 MPU6050 - Wi-Fi Live HAR")
        self.root.geometry("930x650")
        self.root.minsize(820, 560)

        self.sock = None
        self.reader_thread = None
        self.stop_event = threading.Event()
        self.incoming_queue = queue.Queue()
        self.model = None
        self.sample_buffer = deque(maxlen=WINDOW_SIZE)
        self.total_samples = 0
        self.window_count = 0
        self.last_probabilities = None

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.units_var = tk.StringVar(value=ESP32_G_UNITS)
        self.model_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.sample_var = tk.StringVar(value="Samples: 0")
        self.prediction_var = tk.StringVar(value="Prediction: ---")
        self.confidence_var = tk.StringVar(value="Confidence: ---")
        self.last_data_var = tk.StringVar(value="Last sample: ---")

        default_model = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trained_model.h5")
        if os.path.isfile(default_model):
            self.model_var.set(default_model)

        self.build_ui()
        self.root.after(50, self.process_incoming_lines)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        pad = {"padx": 8, "pady": 6}

        connection = ttk.LabelFrame(self.root, text="Wi-Fi TCP connection")
        connection.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(connection, text="ESP32 IP:").grid(row=0, column=0, **pad)
        ttk.Entry(connection, textvariable=self.host_var, width=18).grid(row=0, column=1, **pad)
        ttk.Label(connection, text="TCP port:").grid(row=0, column=2, **pad)
        ttk.Entry(connection, textvariable=self.port_var, width=8).grid(row=0, column=3, **pad)
        ttk.Label(connection, text="Input units:").grid(row=0, column=4, **pad)
        ttk.Combobox(
            connection,
            textvariable=self.units_var,
            values=(ESP32_G_UNITS, DATASET_UNITS),
            state="readonly",
            width=24,
        ).grid(row=0, column=5, **pad)
        self.connect_button = ttk.Button(connection, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=6, **pad)
        ttk.Label(connection, textvariable=self.status_var, foreground="#174a8b").grid(
            row=0, column=7, sticky="w", **pad
        )

        model_frame = ttk.LabelFrame(self.root, text="Model")
        model_frame.pack(fill="x", padx=10, pady=5)
        ttk.Entry(model_frame, textvariable=self.model_var).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(model_frame, text="Select .h5", command=self.select_model).pack(side="left", padx=4)
        ttk.Button(model_frame, text="Load model", command=self.load_model_from_ui).pack(side="left", padx=8)

        info = ttk.LabelFrame(self.root, text="Live result")
        info.pack(fill="x", padx=10, pady=5)
        ttk.Label(info, textvariable=self.prediction_var, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Label(info, textvariable=self.confidence_var, font=("Segoe UI", 12)).pack(anchor="w", padx=12, pady=2)
        ttk.Label(info, textvariable=self.sample_var).pack(anchor="w", padx=12, pady=2)
        ttk.Label(info, textvariable=self.last_data_var, font=("Consolas", 9)).pack(anchor="w", padx=12, pady=(2, 10))

        table_frame = ttk.LabelFrame(self.root, text="Class probabilities")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("class", "probability")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("class", text="Class")
        self.tree.heading("probability", text="Probability")
        self.tree.column("class", width=250, anchor="w")
        self.tree.column("probability", width=180, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tree.configure(yscrollcommand=scrollbar.set)

        notes = (
            "Expected stream: ax,ay,az,gx,gy,gz | 20 Hz | window=40 | overlap=10 | "
            "prediction step=30 | input: g + deg/s | model: m/s² + rad/s"
        )
        ttk.Label(self.root, text=notes, foreground="#555555").pack(anchor="w", padx=12, pady=(0, 8))

    def select_model(self):
        path = filedialog.askopenfilename(
            title="Select trained model",
            filetypes=[("Keras model", "*.h5 *.keras"), ("All files", "*.*")],
        )
        if path:
            self.model_var.set(path)

    def load_model_from_ui(self):
        path = self.model_var.get().strip()
        if not path:
            messagebox.showwarning("Model", "Select a .h5 or .keras model first.")
            return False
        if not os.path.isfile(path):
            messagebox.showerror("Model", f"Model file not found:\n{path}")
            return False

        try:
            model = tf.keras.models.load_model(path, compile=False)
            shape = model.input_shape
            if isinstance(shape, list):
                shape = shape[0]
            if len(shape) != 3 or shape[-2] != WINDOW_SIZE or shape[-1] != FEATURE_COUNT:
                raise ValueError(
                    f"Model input shape is {shape}; expected (None, {WINDOW_SIZE}, {FEATURE_COUNT})."
                )
            self.model = model
            self.status_var.set(f"Model loaded: {os.path.basename(path)}")
            return True
        except Exception as exc:
            self.model = None
            messagebox.showerror("Model load error", str(exc))
            return False

    def toggle_connection(self):
        if self.sock is not None:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        if self.model is None and not self.load_model_from_ui():
            return

        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError("TCP port must be between 1 and 65535.")
        except Exception as exc:
            messagebox.showerror("Connection", str(exc))
            return

        try:
            sock = socket.create_connection((host, port), timeout=5.0)
            sock.settimeout(1.0)
            self.sock = sock
        except Exception as exc:
            messagebox.showerror(
                "Connection failed",
                f"Could not connect to {host}:{port}.\n\n{exc}\n\n"
                "Connect the laptop to ESP32-MPU6050 first.",
            )
            return

        self.sample_buffer.clear()
        self.total_samples = 0
        self.window_count = 0
        self.last_probabilities = None
        self.prediction_var.set("Prediction: ---")
        self.confidence_var.set("Confidence: ---")
        self.sample_var.set("Samples: 0 | Predictions: 0")
        self.last_data_var.set("Last sample: ---")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.stop_event.clear()
        self.status_var.set(f"Connected to {host}:{port}")
        self.connect_button.configure(text="Disconnect")
        self.reader_thread = threading.Thread(target=self.reader_worker, daemon=True)
        self.reader_thread.start()

    def disconnect(self):
        self.stop_event.set()
        sock = self.sock
        self.sock = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        self.connect_button.configure(text="Connect")
        self.status_var.set("Disconnected")

    def reader_worker(self):
        sock = self.sock
        if sock is None:
            return

        buffer = b""
        while not self.stop_event.is_set():
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    self.incoming_queue.put(("status", "ESP32 closed the connection."))
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.decode("ascii", errors="ignore").strip()
                    if line:
                        self.incoming_queue.put(("data", line))
            except socket.timeout:
                continue
            except OSError as exc:
                if not self.stop_event.is_set():
                    self.incoming_queue.put(("status", f"Socket error: {exc}"))
                break

        self.incoming_queue.put(("disconnected", ""))

    def process_incoming_lines(self):
        try:
            while True:
                kind, payload = self.incoming_queue.get_nowait()
                if kind == "data":
                    sample = parse_stream_line(payload)
                    if sample is not None:
                        self.process_sample(sample)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "disconnected":
                    if self.sock is not None:
                        self.sock = None
                        self.connect_button.configure(text="Connect")
                        self.status_var.set("Disconnected")
        except queue.Empty:
            pass
        self.root.after(50, self.process_incoming_lines)

    def process_sample(self, sample):
        # This is intentionally the same conversion used by the Serial Live
        # program when "ESP32: g + deg/s" is selected.
        converted = convert_units(sample, self.units_var.get())
        self.sample_buffer.append(converted.tolist())

        self.total_samples += 1
        self.sample_var.set(
            f"Samples received: {self.total_samples} | "
            f"Predictions: {self.window_count}"
        )
        self.last_data_var.set(
            "Converted sample (m/s²,rad/s): "
            + ", ".join(f"{x:.5f}" for x in converted)
        )

        # Exact Serial Live window schedule:
        # 0..39, then 30..69, then 60..99, ...
        if self.model is None:
            return
        if not (
            len(self.sample_buffer) == WINDOW_SIZE
            and (self.total_samples - WINDOW_SIZE) % STEP_SIZE == 0
        ):
            return

        window = np.asarray(self.sample_buffer, dtype=np.float32)
        try:
            output = self.model.predict(window[np.newaxis, :, :], verbose=0)
            if isinstance(output, list):
                output = output[0]
            probabilities = np.asarray(output[0], dtype=np.float32)
            if probabilities.ndim != 1 or len(probabilities) == 0:
                raise ValueError("Model output is not a valid one-dimensional probability vector.")

            best_index = int(np.argmax(probabilities))
            best_probability = float(probabilities[best_index])
            prediction_name = class_label(best_index, len(probabilities))
            self.prediction_var.set(f"Prediction: {prediction_name}")
            self.confidence_var.set(f"Confidence: {best_probability * 100.0:.2f}%")
            self.update_probability_table(probabilities)
            self.window_count += 1
            self.sample_var.set(
                f"Samples received: {self.total_samples} | "
                f"Predictions: {self.window_count}"
            )
        except Exception as exc:
            self.status_var.set(f"Prediction error: {exc}")

    def update_probability_table(self, probabilities):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, probability in sorted(
            ((class_label(index, len(probabilities)), value)
             for index, value in enumerate(probabilities)),
            key=lambda pair: pair[1],
            reverse=True,
        ):
            self.tree.insert("", "end", values=(name, f"{probability * 100.0:.2f}%"))

    def on_close(self):
        self.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    WiFiLiveHARApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
