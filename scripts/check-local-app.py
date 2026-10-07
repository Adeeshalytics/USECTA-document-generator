"""Exercise local app initialization and start/reopen/stop on the host OS."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['USECTA_LOCAL_MODE'] = '1'


def main():
    # Check app execution independently of the default browser and without saving fake records.
    with tempfile.TemporaryDirectory(prefix='usecta-ui-check-') as temp:
        os.environ['USECTA_DATA_DIR'] = temp
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
        if app.exception or len(app.tabs) != 5:
            raise RuntimeError('Local app did not load the five workflow tabs.')
        del os.environ['USECTA_DATA_DIR']
    import desktop
    process = subprocess.Popen([sys.executable, str(ROOT / 'desktop.py'), '--no-browser'], cwd=ROOT)
    try:
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            state = desktop.control(desktop.read_state())
            if state and state['ready']:
                break
            if process.poll() is not None:
                raise RuntimeError('Desktop launcher exited during startup.')
            time.sleep(.25)
        else:
            raise RuntimeError('Desktop launcher readiness check timed out.')
        subprocess.run([sys.executable, str(ROOT / 'desktop.py'), '--no-browser'], check=True, timeout=10, cwd=ROOT)
        assert desktop.control(desktop.read_state())['url'] == state['url']
        subprocess.run([sys.executable, str(ROOT / 'desktop.py'), '--stop'], check=True, timeout=10, cwd=ROOT)
        process.wait(timeout=15)
        assert process.returncode == 0
        assert not desktop.STATE.exists()
    finally:
        if process.poll() is None:
            desktop.control(desktop.read_state(), 'stop')
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print('Local app tabs, desktop startup, repeat launch and stop checks passed.')


if __name__ == '__main__':
    main()
