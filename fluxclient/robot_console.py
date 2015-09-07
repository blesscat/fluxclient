
from tempfile import NamedTemporaryFile
from select import select
import logging
import socket
import shlex
import os

logger = logging.getLogger(__name__)


class RobotConsole(object):
    _mode = "standard"
    _thread = None
    _raw_sock = None

    def __init__(self, robot_obj):
        self.robot_obj = robot_obj
        self.simple_mapping = {
            "start": robot_obj.start_play,
            "pause": robot_obj.pause_play,
            "resume": robot_obj.resume_play,
            "abort": robot_obj.abort_play,
            "report": robot_obj.report_play,
            "position": robot_obj.position,
            "quit": robot_obj.quit_task,
            "kick": robot_obj.kick,

            "scan": robot_obj.begin_scan,
            "scan_backward": robot_obj.scan_backward,
            "scan_next": robot_obj.scan_next,

            "maintain": robot_obj.begin_maintain,
            "home": robot_obj.maintain_home,
            "reset_mb": robot_obj.reset_mb,
        }

        self.cmd_mapping = {
            "ls": self.list_file,
            "select": self.select_file,
            "fileinfo": self.fileinfo,
            "mkdir": self.mkdir,
            "rmdir": self.rmdir,
            "rmfile": self.rmfile,
            "cp": self.cpfile,
            "upload": self.upload_file,
            "update_fw": self.update_fw,
            "oneshot": self.oneshot,
            "scanimages": self.scanimages,
            "raw": self.raw_mode,
            "set": self.set_setting,
        }

    def on_cmd(self, arguments):
        if self._mode == "raw":
            if arguments == "quit":
                self.quit_raw_mode()
            else:
                self._raw_sock.send(arguments.encode() + b"\n")
        else:
            args = arguments.split(" ", 1)
            cmd = args[0]

            try:
                if cmd in self.simple_mapping:
                    self.simple_cmd(self.simple_mapping[cmd], *args[1:])
                elif cmd in self.cmd_mapping:
                    func_ptr = self.cmd_mapping[cmd]
                    func_ptr(*args[1:])
                else:
                    logger.error("Unknow Command Q")

            except RuntimeError as e:
                logger.error("RuntimeError%s" % repr(e.args))

    def simple_cmd(self, func_ptr, *args):
        logger.info(func_ptr(*args))

    def list_file(self, path):
        path = shlex.split(path)[0]
        if path == "SD":
            nodes = self.robot_obj.list_sd_files("")
        elif path.startswith("SD/"):
            nodes = self.robot_obj.list_sd_files(path[3:])
        elif path == "USB":
            nodes = self.robot_obj.list_usb_files("")
        elif path == "USB/":
            nodes = self.robot_obj.list_usb_files(path[4:])
        else:
            raise RuntimeError("NOT_FOUND")

        for is_dir, node in nodes:
            if is_dir:
                logger.info("DIR %s" % os.path.join(path, node))
            else:
                logger.info("FILE %s" % os.path.join(path, node))
        logger.info("ls done.")

    def select_file(self, path):
        path = shlex.split(path)[0]
        if path.startswith("SD/"):
            self.simple_cmd(self.robot_obj.select_sd_file, path[3:])
            ret = self.robot_obj.select_sd_file(path[3:])
        elif path.startswith("USB/"):
            self.simple_cmd(self.robot_obj.select_usb_file, path[4:])
        else:
            raise RuntimeError("NOT_FOUND", "BAD_ENTRY")

    def fileinfo(self, path):
        path = shlex.split(path)[0]
        if path.startswith("SD/"):
            self.simple_cmd(self.robot_obj.sd_fileinfo, path[3:])
            ret = self.robot_obj.select_sd_file(path[3:])
        elif path.startswith("USB/"):
            self.simple_cmd(self.robot_obj.usb_fileinfo, path[4:])
        else:
            raise RuntimeError("NOT_FOUND", "BAD_ENTRY")

    def mkdir(self, path):
        path = shlex.split(path)[0]
        if path.startswith("SD/"):
            self.simple_cmd(self.robot_obj.sd_mkdir, path[3:])
        else:
            raise RuntimeError("NOT_SUPPORT", "SD_ONLY")

    def rmdir(self, path):
        path = shlex.split(path)[0]
        if path.startswith("SD/"):
            self.simple_cmd(self.robot_obj.sd_rmdir, path[3:])
        else:
            raise RuntimeError("NOT_SUPPORT", "SD_ONLY")

    def rmfile(self, path):
        path = shlex.split(path)[0]
        if path.startswith("SD/"):
            self.simple_cmd(self.robot_obj.sd_rmfile, path[3:])
        else:
            raise RuntimeError("NOT_SUPPORT", "SD_ONLY")

    def cpfile(self, args):
        try:
            source, target = shlex.split(args)
            if source.startswith("SD/"):
                source_target = "SD"
                source = source[3:]
            elif source.startswith("USB/"):
                source_target = "USB"
                source = source[4:]
            else:
                raise RuntimeError("NOT_SUPPORT", "BAD_ENTRY")

            if target.startswith("SD/"):
                target = target[3:]
                self.simple_cmd(self.robot_obj.cpfile, source_target, source,
                                "SD", target)
            else:
                raise RuntimeError("NOT_SUPPORT", "SD_ONLY")
        except ValueError:
            raise RuntimeError("BAD_PARAMS")

    def upload_file(self, filename):
        filename = shlex.split(filename)[0]
        self.robot_obj.upload_file(
            filename, progress_callback=self.log_progress_callback)

    def update_fw(self, filename):
        self.robot_obj.upload_file(
            filename.rstrip(), cmd="update_fw",
            progress_callback=self.log_progress_callback)

    def oneshot(self, filename=None):
        images = self.robot_obj.oneshot()
        tempfiles = []
        for mime, buf in images:
            ntf = NamedTemporaryFile(suffix=".jpg", delete=False)
            ntf.write(buf)
            tempfiles.append(ntf)

        os.system("open " + " ".join([n.name for n in tempfiles]))

    def scanimages(self, filename=None):
        images = self.robot_obj.scanimages()
        tempfiles = []
        for mime, buf in images:
            ntf = NamedTemporaryFile(suffix=".jpg", delete=False)
            ntf.write(buf)
            tempfiles.append(ntf)

        os.system("open " + " ".join([n.name for n in tempfiles]))

    def set_setting(self, line):
        params = line.split(" ")
        if len(params) == 2:
            logger.info(
                self.robot_obj.set_setting(key=params[0], value=params[1])
            )
        else:
            logger.info("BAD_PARAMS")

    def raw_mode(self):
        import threading
        self._raw_sock = self.robot_obj.raw_mode()
        self._mode = "raw"

        self._thread = threading.Thread(target=self.__raw_mode_thread)
        self._thread.setDaemon(True)
        self._thread.start()
        logger.info("raw mode ->")

    def quit_raw_mode(self):
        self._mode = "standard"
        sock = self._raw_sock
        self._raw_sock = None
        if self._thread:
            self._thread.join()
        sock.send(b"quit")
        logger.info(self.robot_obj.get_resp().decode("ascii", "ignore"))

    def log_progress_callback(self, robot, progress, total):
        logger.info("Processing %3.1f %% (%i of %i)" %
                    (progress / total * 100.0, progress, total))

    def __raw_mode_thread(self):
        try:
            while self._mode == "raw":
                rl = select((self._raw_sock, ), (), (), 0.1)[0]
                if rl:
                    buf = rl[0].recv(4096).decode("utf8", "ignore")
                    if buf:
                        for ln in buf.split("\n"):
                            logger.info(ln.rstrip("\r\x00"))
                    else:
                        logger.error("Connection closed")
                        return

        except Exception:
            self._mode == "standard"
            logger.exception("Raw mode fatel, your session my be broken")
