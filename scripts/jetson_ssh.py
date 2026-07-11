import argparse
import getpass
import os
import sys
from pathlib import Path

import paramiko


def write_text(text):
    if not text:
        return
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def connect(args):
    password = args.password or os.environ.get("JETSON_PASSWORD")
    if password is None:
        password = getpass.getpass("Jetson password: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=args.host,
        username=args.user,
        password=password,
        timeout=args.timeout,
        banner_timeout=args.timeout,
        auth_timeout=args.timeout,
    )
    return client


def run_exec(args):
    command = " ".join(args.remote_command)
    with connect(args) as client:
        stdin, stdout, stderr = client.exec_command(command, get_pty=args.pty)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        write_text(out)
        write_text(err)
        raise SystemExit(exit_code)


def run_put(args):
    local = Path(args.local)
    if not local.is_file():
        raise SystemExit(f"local file does not exist: {local}")

    with connect(args) as client:
        with client.open_sftp() as sftp:
            remote_parent = str(Path(args.remote).parent).replace("\\", "/")
            client.exec_command(f"mkdir -p '{remote_parent}'")[1].channel.recv_exit_status()
            sftp.put(str(local), args.remote)
            print(f"uploaded: {local} -> {args.remote}")


def run_get(args):
    local = Path(args.local)
    local.parent.mkdir(parents=True, exist_ok=True)

    with connect(args) as client:
        with client.open_sftp() as sftp:
            sftp.get(args.remote, str(local))
            print(f"downloaded: {args.remote} -> {local}")


def add_common(parser):
    parser.add_argument("--host", default="192.168.55.1")
    parser.add_argument("--user", default="nvidia")
    parser.add_argument("--password", default=None)
    parser.add_argument("--timeout", type=float, default=10.0)


def main():
    parser = argparse.ArgumentParser(description="Small Paramiko helper for Jetson SSH/SFTP tasks.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    exec_parser = subparsers.add_parser("exec", help="Run a remote shell command")
    add_common(exec_parser)
    exec_parser.add_argument("--pty", action="store_true", help="Request a pseudo terminal")
    exec_parser.add_argument("remote_command", nargs=argparse.REMAINDER)
    exec_parser.set_defaults(func=run_exec)

    put_parser = subparsers.add_parser("put", help="Upload one local file")
    add_common(put_parser)
    put_parser.add_argument("local")
    put_parser.add_argument("remote")
    put_parser.set_defaults(func=run_put)

    get_parser = subparsers.add_parser("get", help="Download one remote file")
    add_common(get_parser)
    get_parser.add_argument("remote")
    get_parser.add_argument("local")
    get_parser.set_defaults(func=run_get)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
