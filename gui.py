import sys
import json
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QComboBox, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal
from utils import load_model, unload_model
import requests

class BotGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Load config.json
        with open('D:/bot_files/config.json', 'r') as f:
            self.config = json.load(f)

        # Set window title
        self.setWindowTitle('Discord Bot GUI')

        # Define layout
        layout = QVBoxLayout()

        # Add dropdown for character prompt selection
        self.prompt_dropdown = QComboBox(self)
        self.prompt_dropdown.addItems(self.config['prompts'].keys())
        layout.addWidget(self.prompt_dropdown)

        # Start/Stop buttons
        self.start_button = QPushButton('Start All (Bot, Text Gen, SD Web UIs)')
        self.start_button.clicked.connect(self.start_bot_and_webui)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton('Stop All Processes')
        self.stop_button.clicked.connect(self.stop_all_processes)
        layout.addWidget(self.stop_button)

        # Reload model button
        self.reload_button = QPushButton('Reload Model')
        self.reload_button.clicked.connect(self.reload_model_in_thread)
        layout.addWidget(self.reload_button)

        # Text widget to show the log output from all processes
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        # Status label
        self.status_label = QLabel('Status: Not running')
        layout.addWidget(self.status_label)

        # Set layout to the window
        self.setLayout(layout)

        # Track the processes for the bot, web UIs, and image bot
        self.bot_process = None
        self.webui_process = None
        self.sd_process = None

    def append_log(self, text):
        """Add text to the log output in the GUI."""
        self.log_output.append(text)
        self.log_output.ensureCursorVisible()

    def start_bot_and_webui(self):
        # Start Ooba Booga WebUI
        if self.webui_process is None:
            self.append_log("Starting WebUI (Ooba Booga)...")
            try:
                self.webui_process = subprocess.Popen(
                    ['D:/Games/SD/text-generation-webui/start_windows.bat'], 
                    shell=True
                )
                self.append_log("WebUI started successfully.")
            except Exception as e:
                self.append_log(f"Error starting WebUI: {e}")

        # Start Discord bot
        if self.bot_process is None:
            self.append_log("Starting img_bot.py from GUI...")
            selected_prompt = self.prompt_dropdown.currentText()
            self.bot_process = subprocess.Popen(
                ['python', 'D:/bot_files/img_bot.py', selected_prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            self.append_log("Discord bot started.")

        # Start Stable Diffusion web UI
        if self.sd_process is None:
            self.append_log("Starting Stable Diffusion Web UI...")
            try:
                self.sd_process = subprocess.Popen(
                    [r"D:\Games\SD\forge\run.bat"],
                    shell=True,
                    cwd=r"D:\Games\SD\forge",
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                self.append_log("Stable Diffusion Web UI started successfully.")
            except Exception as e:
                self.append_log(f"Error starting Stable Diffusion: {e}")

        self.status_label.setText('Status: All processes (Bot, Web UIs) are running')

    def stop_all_processes(self):
        # Stop the bot process
        if self.bot_process:
            self.append_log("Stopping Discord bot...")
            self.bot_process.terminate()
            self.bot_process = None

        # Stop the web UI process
        if self.webui_process:
            self.append_log("Stopping WebUI...")
            self.webui_process.terminate()
            self.webui_process = None

        # Stop the Stable Diffusion web UI process
        if self.sd_process:
            self.append_log("Stopping Stable Diffusion Web UI...")
            self.sd_process.terminate()
            self.sd_process = None

        self.status_label.setText('Status: All processes stopped')
        self.append_log('All processes stopped.')

    def reload_model_in_thread(self):
        """Reload the model in a separate thread to avoid freezing the GUI."""
        self.thread = ModelReloadThread()
        self.thread.finished.connect(self.on_reload_finished)
        self.thread.start()

    def on_reload_finished(self, result):
        if result == "success":
            self.append_log("Model reloaded successfully.")
        else:
            self.append_log(f"Error reloading model: {result}")
        self.status_label.setText('Status: Model reloaded')

    def monitor_process(self, process, process_name):
        """Monitor the output of a process in a separate thread."""
        self.thread = ProcessMonitorThread(process, process_name)
        self.thread.update_log.connect(self.append_log)
        self.thread.start()


class ProcessMonitorThread(QThread):
    update_log = pyqtSignal(str)

    def __init__(self, process, process_name):
        super().__init__()
        self.process = process
        self.process_name = process_name

    def run(self):
        # Stream stdout and stderr from the process and emit log updates
        for line in self.process.stdout:
            self.update_log.emit(f"{self.process_name}: {line.strip()}")
        for err in self.process.stderr:
            self.update_log.emit(f"{self.process_name} (ERROR): {err.strip()}")


class ModelReloadThread(QThread):
    finished = pyqtSignal(str)

    def run(self):
        try:
            unload_model()
            load_model()
            self.finished.emit("success")
        except Exception as e:
            self.finished.emit(str(e))


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Create the GUI window
    window = BotGUI()
    window.show()

    sys.exit(app.exec_())
