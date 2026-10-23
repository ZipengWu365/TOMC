"""Asynchronous, read-only allowance polling through the official Codex app-server."""

import json
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .quota import codex_executable, quota_windows


class QuotaReader(QObject):
    updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.errorOccurred.connect(lambda _: self.failed())
        self.process.finished.connect(lambda *_: self.failed())
        self.process.started.connect(self.initialize)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.failed)
        self.poll = QTimer(self)
        self.poll.setInterval(60000)
        self.poll.timeout.connect(self.request)
        self.buffer, self.ready, self.stopped = b"", False, False
        self.restarting = False
        self.next_id, self.pending = 1, None

    def start(self):
        if self.stopped:
            return
        self.ready, self.pending, self.buffer = False, None, b""
        executable = codex_executable()
        if not executable:
            self.updated.emit({"status": "unavailable", "windows": []})
            self.poll.start()
            return
        self.process.start(executable, ["app-server"])
        self.timeout.start(15000)

    def send(self, message):
        self.process.write((json.dumps(message)+"\n").encode())

    def initialize(self):
        self.send({"id": 0, "method": "initialize", "params": {
            "clientInfo": {"name": "tomc_allowance", "title": "TOMC", "version": "0.1.4"}}})

    def request(self):
        if self.stopped or self.pending is not None:
            return
        if (not self.ready and self.timeout.isActive()
                and self.process.state() != QProcess.ProcessState.NotRunning):
            return  # Let an in-flight initialization finish before reconnecting.
        if not self.ready or self.process.state() == QProcess.ProcessState.NotRunning:
            self.restarting = True
            self.process.closeWriteChannel()
            if not self.process.waitForFinished(30):
                self.process.kill()
                self.process.waitForFinished(100)
            self.restarting = False
            self.start()
            return
        self.pending = self.next_id
        self.next_id += 1
        self.send({"id": self.pending, "method": "account/rateLimits/read"})
        self.timeout.start(15000)

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                message = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if message.get("id") == 0:
                if "error" in message:
                    self.failed()
                    return
                self.ready = True
                self.timeout.stop()
                self.send({"method": "initialized", "params": {}})
                self.poll.start()
                self.request()
            elif self.pending is not None and message.get("id") == self.pending:
                self.pending = None
                self.timeout.stop()
                windows = quota_windows(message.get("result", {}))
                self.updated.emit({"status": "ready" if windows else "unavailable",
                                   "windows": windows, "read_at": time.time()})
            elif message.get("method") == "account/rateLimits/updated":
                windows = quota_windows(message.get("params", {}))
                self.updated.emit({"status": "ready" if windows else "unavailable",
                                   "windows": windows, "read_at": time.time()})

    def failed(self):
        if self.stopped or self.restarting:
            return
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.Running or self.pending is None:
            self.ready = False
        self.pending = None
        self.updated.emit({"status": "unavailable", "windows": []})
        # Retry connection or request on the next bounded tick, never a busy loop.
        self.poll.start()

    def stop(self):
        self.stopped = True
        self.poll.stop()
        self.timeout.stop()
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(300):
            self.process.kill()  # Only the helper this widget owns; never another Codex process.
            self.process.waitForFinished(300)
