
import threading
import argparse
import sys
import re


def is_serial(target):
    return True if re.match("[0-9A-Z]{25}", target) else False


def parse_ipaddr(target):
    if ":" in target:
        addr, port = target.split(":")
        return (addr, int(port))
    else:
        return (target, 23811)


def select_ipaddr(remote_addrs):
    return (remote_addrs[0][0], 23811)


def parse_target(options, output):
    from fluxclient.upnp_task import UpnpTask
    from time import sleep

    def lookup_callback(discover):
        output(".")

    if is_serial(options.target):
        output("Discover...")
        task = UpnpTask(options.target, lookup_callback=lookup_callback)
        ipaddr = select_ipaddr(task.remote_addrs)
        output(" OK\n")
        output("Serial: %s\nModel: %s\nIP Addr: %s\n" %
               (task.serial.hex, task.model_id, ipaddr[0]))

        task.require_auth()

        try:
            resp = task.require_robot()
            if resp is not None:
                output("Robot launching...\n")
                sleep(0.5)
        except RuntimeError as e:
            if e.args[0] == "ALREADY_RUNNING":
                output("Robot already running\n")
            else:
                raise

        return ipaddr, task.remote_keyobj
    else:
        return parse_ipaddr(options.target), None


def robot_shell_reciver(robot_client, console):
    while True:
        buf = robot_client.recv(4096)
        if buf:
            console.append_log(buf.decode("utf-8", "ignore").strip("\x00") +
                               "\n")
        else:
            console.append_log("Disconnected!!\n")
            return


def ipython_shell_reciver(robot_client):
    while True:
        buf = robot_client.recv(4096)
        if buf:
            print(buf.decode("utf-8", "ignore") + "\n")
        else:
            print("Disconnected!!")
            return


def robot_shell(options):
    from fluxclient.console import Console
    from fluxclient.robot import RobotClient

    with Console() as console:
        console.setup()

        try:
            ipaddr, keyobj = parse_target(options, output=console.append_log)
            robot_client = RobotClient(ipaddr=ipaddr, server_key=keyobj,
                                       stdout=console.append_log)

            t = threading.Thread(target=robot_shell_reciver,
                                 args=(robot_client, console))
            t.setDaemon(True)
            t.start()

            while True:
                cmd = console.read_cmd()
                if cmd:
                    robot_client.send_cmd(cmd.encode())

        except Exception:
            from io import StringIO
            import traceback

            f = StringIO()
            errargs = sys.exc_info()

            traceback.print_exception(*errargs, file=f)
            console.append_log(f.getvalue())
            console.append_log("Press enter quit")
            cmd = console.read_cmd()
            return


def ipython_shell(options):
    from fluxclient.robot import RobotClient
    import IPython

    ipaddr, keyobj = parse_target(options, output=print)
    robot_client = RobotClient(ipaddr=ipaddr, server_key=keyobj, stdout=print)

    t = threading.Thread(target=ipython_shell_reciver, args=(robot_client, ))
    t.setDaemon(True)
    t.start()

    print(">> robot_client")
    IPython.embed()


def simple_shell(options):
    from fluxclient.robot import RobotClient

    ipaddr, keyobj = parse_target(options, output=print)
    robot_client = RobotClient(ipaddr=ipaddr, server_key=keyobj, stdout=print)

    t = threading.Thread(target=ipython_shell_reciver, args=(robot_client, ))
    t.setDaemon(True)
    t.start()

    print("Console Ready")

    while True:
        r = sys.stdin.readline()
        robot_client.send_cmd(r.encode())


def do_kill(options):
    if is_serial(options.target):
        from fluxclient.upnp_task import UpnpTask

        task = UpnpTask(options.target)
        ipaddr = select_ipaddr(task.remote_addrs)
        print("Serial: %s\nModel: %s\nIP Addr: %s\n" %
              (task.serial.hex, task.model_id, ipaddr[0]))

        task.require_auth()
        task.kill_control()
        print("Kill signal sent.")
    else:
        raise RuntimeError("Kill must give serial, not IP addr")


def main():
    parser = argparse.ArgumentParser(description='flux robot')

    parser.add_argument(dest='target', type=str,
                        help="Printer connect with. It can be printer serial "
                             "or IP address like 192.168.1.1 or "
                             "192.168.1.1:23811")
    parser.add_argument('--kill', dest='do_kill', action='store_const',
                        const=True, default=False, help='Use python shell')
    parser.add_argument('--ipython', dest='ipython', action='store_const',
                        const=True, default=False, help='Use python shell')
    parser.add_argument('--simple', dest='simple', action='store_const',
                        const=True, default=False, help='Use python shell')
    options = parser.parse_args()

    if options.do_kill:
        do_kill(options)
    elif options.ipython:
        ipython_shell(options)
    elif options.simple:
        simple_shell(options)
    else:
        robot_shell(options)

    return 0

if __name__ == "__main__":
    sys.exit(main())
