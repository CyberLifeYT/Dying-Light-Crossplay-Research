"""Attach eos_logger.js to DyingLightGame.exe as soon as it appears; write the log file.

usage:  python eos_attach.py [--log ..\\logs\\run1.log]
Start this first, then launch Dying Light from the Epic launcher. Ctrl+C to stop.
"""
import argparse, datetime, os, sys, time
import frida

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--log", default=os.path.join(HERE, "..", "logs",
                datetime.datetime.now().strftime("eos_%Y%m%d_%H%M%S.log")))
ap.add_argument("--process", default="DyingLightGame.exe")
args = ap.parse_args()
os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

dev = frida.get_local_device()
print(f"waiting for {args.process} ... (launch the game from Epic now)")
pid = None
while pid is None:
    pid = next((p.pid for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()), None)
    if pid is None:
        time.sleep(0.05)

session = dev.attach(pid)
out = open(args.log, "a", encoding="utf-8", buffering=1)
def on_message(msg, _data):
    out.write(f"{datetime.datetime.now().isoformat()}\tFRIDA\t{msg}\n")
script = session.create_script(open(os.path.join(HERE, "eos_logger.js"), encoding="utf-8").read())
script.set_log_handler(lambda level, text: (out.write(text + "\n"), print(text)))
script.on("message", on_message)
script.load()
print(f"attached to pid {pid}; logging to {os.path.abspath(args.log)}")
try:
    while not session.is_detached:
        time.sleep(0.5)
    print("game exited / session detached")
except KeyboardInterrupt:
    pass
finally:
    try:
        session.detach()
    except Exception:
        pass
    out.close()
