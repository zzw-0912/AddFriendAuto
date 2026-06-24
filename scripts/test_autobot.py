"""
Test automation script for FriendAuto.
Simulates the protocol that the real automation script will use.
Opens Notepad, types "123456", then exits.
"""
import json
import subprocess
import sys
import time


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "test_run_001"

    print(json.dumps({"run_id": run_id, "event": "started", "message": "Starting test script", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}))
    sys.stdout.flush()

    try:
        proc = subprocess.Popen(["notepad.exe"])
        time.sleep(1.5)

        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("记事本") or gw.getWindowsWithTitle("Notepad")
        if not wins:
            wins = gw.getAllWindows()
            wins = [w for w in wins if "记事本" in w.title or "Notepad" in w.title or "无标题" in w.title]

        if wins:
            wins[0].activate()
            time.sleep(0.3)

        import keyboard
        keyboard.write("123456")
        time.sleep(0.5)

        proc.terminate()
        time.sleep(0.3)
        keyboard.press_and_release("alt+n")

        print(json.dumps({"run_id": run_id, "contact_id": "test_contact_001", "event": "success", "message": "添加成功", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}))
        sys.stdout.flush()

        print(json.dumps({"run_id": run_id, "event": "finished", "message": "Task completed", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}))
        sys.stdout.flush()

    except Exception as e:
        print(json.dumps({"run_id": run_id, "event": "error", "message": str(e), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}))
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
