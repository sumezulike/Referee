import sys
import argparse
import subprocess


def parse_cli_arguments():
    parser = argparse.ArgumentParser(description="Refereebot - Three strikes and you're out")
    parser.add_argument("--auto-restart", "-a",
                        help="Autorestarts Referee in case of issues",
                        action="store_true")
    return parser.parse_args()


def run_ref(autorestart):
    interpreter = sys.executable

    if interpreter is None:  # This should never happen
        raise RuntimeError("Couldn't find Python's interpreter")

    cmd = (interpreter, "ref.py")

    while True:
        try:
            code = subprocess.call(cmd)
        except KeyboardInterrupt:
            code = 0
            break
        else:
            if code == 0:
                break
            elif code == 26:
                print("Restarting Referee...")
                continue
            else:
                if not autorestart:
                    break

    print("Referee has been terminated. Exit code: {}]".format(code))


args = parse_cli_arguments()
if __name__ == "__main__":
    print("Starting Referee...")
    run_ref(autorestart=args.auto_restart)
