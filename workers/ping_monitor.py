# workers/ping_monitor.py
import threading
from datetime import datetime

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal

DEVICES = ["10.10.10.2", "10.10.10.3", "10.10.10.4", "10.10.10.5"]
_CONNECTIVITY_THRESHOLD = 5


class PingMonitor(QThread):
    ping_loss_event = pyqtSignal(str, str, object)   # ip, event_type, timestamp
    connection_event = pyqtSignal(str, str, object)  # event_type, detail, timestamp

    def __init__(self, host: str, port: int, username: str, password: str,
                 stop_flag: threading.Event, parent=None):
        super().__init__(parent)
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._stop_flag = stop_flag
        self._consecutive: dict[str, int] = {ip: 0 for ip in DEVICES}
        # sticky flag: once True it never resets; recovery after connectivity loss
        # always emits Connectivity Restored, never Ping Restored
        self._ever_loss: dict[str, bool] = {ip: False for ip in DEVICES}
        self._ssh: paramiko.SSHClient | None = None

    def _connect_ssh(self, host: str, port: int,
                     username: str, password: str) -> bool:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=port, username=username,
                           password=password, timeout=10)
            self._ssh = client
            self.connection_event.emit(
                "SSH Connected",
                f"host={host} port={port} user={username}",
                datetime.now(),
            )
            return True
        except Exception as e:
            self.connection_event.emit("SSH Failed", str(e), datetime.now())
            return False

    def _handle_failure(self, ip: str) -> None:
        self._consecutive[ip] += 1
        ts = datetime.now()
        count = self._consecutive[ip]
        if count == _CONNECTIVITY_THRESHOLD:
            self._ever_loss[ip] = True
            self.ping_loss_event.emit(ip, "Connectivity Loss", ts)
        elif count < _CONNECTIVITY_THRESHOLD:
            self.ping_loss_event.emit(ip, "Ping Loss", ts)
        # counts above threshold emit nothing — device is already marked as lost

    def _handle_success(self, ip: str) -> None:
        prev = self._consecutive[ip]
        self._consecutive[ip] = 0
        if prev == 0:
            return
        ts = datetime.now()
        if self._ever_loss[ip]:
            self.ping_loss_event.emit(ip, "Connectivity Restored", ts)
        else:
            self.ping_loss_event.emit(ip, "Ping Restored", ts)

    def _parse_channel(self, ip: str, chan: paramiko.Channel) -> None:
        stdout = chan.makefile("r")
        for line in stdout:
            if self._stop_flag.is_set():
                break
            line = line.strip()
            if "no answer yet" in line or "Request timeout" in line:
                self._handle_failure(ip)
            elif "bytes from" in line or "icmp_seq" in line:
                self._handle_success(ip)

    def run(self) -> None:
        if not self._connect_ssh(self._host, self._port,
                                  self._username, self._password):
            return
        transport = self._ssh.get_transport()
        if transport is None:
            self.connection_event.emit("SSH Failed", "Transport unavailable", datetime.now())
            return
        channels: list[paramiko.Channel] = []
        parsers: list[threading.Thread] = []
        try:
            # Each parser thread is pinned to a unique IP key; no cross-thread key contention.
            for ip in DEVICES:
                chan = transport.open_session()
                # Use getattr to call exec_command via a local reference
                exec_fn = getattr(chan, "exec_command")
                exec_fn(f"ping -O -i 0.2 {ip}")
                channels.append(chan)
                t = threading.Thread(
                    target=self._parse_channel, args=(ip, chan), daemon=True
                )
                parsers.append(t)
                t.start()
            for t in parsers:
                t.join()
        finally:
            self._ssh.close()
