"""Robotic Hand Sensors and Control Systems Telemetry Display Application.

Combined final project for:
 1. Actuators and Power Electronics (METE3100U), Dr. Aaron Yurkewich.
 2. Sensors and Instrumentation (METE3200U), Dr. Shabnam Pejhan.

Code written by: Daniel Jeon (https://github.com/danielljeon).
"""

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import QTimer, QThread, Signal, Slot, QObject

import pyqtgraph as pg
from digi.xbee.devices import XBeeDevice, XBeeMessage


class BackendWorker(QObject):
    # Signal that sends a dictionary with sensor data.
    sensor_data_signal = Signal(dict)

    def __init__(self, xbee_port, xbee_baud_rate=115200, parent=None):
        super().__init__(parent)
        self.xbee_port = xbee_port
        self.xbee_baud_rate = xbee_baud_rate
        self.xbee = None

    def start(self):
        # Open the XBee device connection.
        self.xbee = XBeeDevice(self.xbee_port, self.xbee_baud_rate)
        self.xbee.open()
        # Register the callback for incoming messages.
        self.xbee.add_data_received_callback(self.handle_xbee_message)

    def handle_xbee_message(self, xbee_message: XBeeMessage):
        try:
            # Message format dictated by sender:
            # "setpoint,command,measurement1,measurement2"
            data_str = xbee_message.data.decode().strip()
            parts = data_str.split(",")
            if len(parts) != 4:
                print("Unexpected message format:", data_str)
                return

            # Convert each part to a float.
            sensor_data = {
                "command": float(parts[1]),
                "setpoint": float(parts[0]),
                "measurement1": float(parts[2]),
                "measurement2": float(parts[3]),
            }
            # Emit the sensor data so the GUI can update.
            self.sensor_data_signal.emit(sensor_data)
        except Exception as e:
            print(f"Error processing XBee message: {e}")

    def stop(self):
        if self.xbee is not None and self.xbee.is_open():
            self.xbee.close()


class LiveGraphWindow(QMainWindow):
    """Live Graph Window with Moving Window.

    Note: Extends PySide6 GUI classes.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Graph Display")
        self.window_size = 100  # Number of most recent data points to display.
        # Use lists to store all data points.
        self.data = {
            "command": [],
            "setpoint": [],
            "measurement1": [],
            "measurement2": [],
        }

        self.plot_widget = pg.PlotWidget(
            title="Robotic Hand Sensors & Controls Data"
        )
        self.plot_widget.addLegend()
        self.curves = {}
        for key, color in zip(
            ["command", "setpoint", "measurement1", "measurement2"],
            ["r", "g", "b", "y"],
        ):
            curve = self.plot_widget.plot([], [], pen=color, name=key)
            self.curves[key] = curve

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.plot_widget)
        self.setCentralWidget(central_widget)

        # Timer to update the plot periodically.
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(100)

    @Slot(dict)
    def update_data(self, sensor_data):
        # Append the new sensor data to each channel.
        for key in self.data.keys():
            self.data[key].append(sensor_data.get(key, 0))

    def update_plot(self):
        # For each channel, display only the last window_size points.
        for key, curve in self.curves.items():
            full_data = self.data[key]
            # Get only the last window_size points.
            y = (
                full_data[-self.window_size :]
                if len(full_data) >= self.window_size
                else full_data
            )
            # Calculate corresponding x values (global index).
            x_start = len(full_data) - len(y)
            x = list(range(x_start, x_start + len(y)))
            curve.setData(x, y)


def main():
    app = QApplication(sys.argv)
    window = LiveGraphWindow()
    window.show()

    xbee_port = "COM8"  # Example COM port connecting to XBee device.
    worker = BackendWorker(xbee_port=xbee_port)
    thread = QThread()
    worker.moveToThread(thread)
    worker.sensor_data_signal.connect(window.update_data)
    thread.started.connect(worker.start)
    thread.start()

    exit_code = app.exec()
    worker.stop()
    thread.quit()
    thread.wait()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
