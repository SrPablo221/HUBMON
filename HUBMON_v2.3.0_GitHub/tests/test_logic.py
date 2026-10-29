"""Offline smoke test for the DDC/CI worker using a simulated monitor."""
import importlib.util
from types import SimpleNamespace
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'hub_monitor.py'
spec = importlib.util.spec_from_file_location('hubmon_test_module', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeMonitor:
    def __init__(self):
        self.input = 0x03
        self.volume = 42
        self.brightness = 61
        self.muted = False
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def get_vcp_capabilities(self):
        return {'model': 'FAKE-MONITOR', 'cmds': {0x60: [0x01, 0x03], 0x62: []}}
    def get_input_source(self): return self.input
    def set_input_source(self, v): self.input = int(v)
    def get_volume(self): return self.volume
    def set_volume(self, v): self.volume = int(v)
    def get_luminance(self): return self.brightness
    def set_luminance(self, v): self.brightness = int(v)
    def get_audio_mute_mode(self): return 1 if self.muted else 2
    def set_audio_mute_mode(self, v): self.muted = int(v) == 1

fake = FakeMonitor()
mod.get_monitors = lambda: [fake]
# _execute_action only needs _read_monitor_info as a static helper on self.
dummy = SimpleNamespace(_read_monitor_info=mod.Hub._read_monitor_info)

infos = mod.Hub._execute_action(dummy, 'detect', {})
assert len(infos) == 1 and infos[0]['model'] == 'FAKE-MONITOR' and infos[0]['volume'] == 42
res = mod.Hub._execute_action(dummy, 'set_volume', {'monitor_index': 0, 'value': 27})
assert res == {'requested': 27, 'actual': 27, 'write_ok': True, 'first_error': None, 'retry_error': None}
res = mod.Hub._execute_action(dummy, 'set_brightness', {'monitor_index': 0, 'value': 73})
assert res == {'requested': 73, 'actual': 73}
assert mod.Hub._execute_action(dummy, 'get_brightness', {'monitor_index': 0}) == 73

# Simulate an intermittent I2C write error: one retry should recover.
class FlakyMonitor(FakeMonitor):
    def __init__(self):
        super().__init__()
        self.fail_once = True
    def set_volume(self, v):
        if self.fail_once:
            self.fail_once = False
            raise OSError('simulated I2C write failure')
        self.volume = int(v)

flaky = FlakyMonitor()
mod.get_monitors = lambda: [flaky]
res = mod.Hub._execute_action(dummy, 'set_volume', {'monitor_index': 0, 'value': 31})
assert res['write_ok'] is True and res['actual'] == 31 and 'simulated I2C' in res['first_error']

# Persistent failures should be reported as failed even if a readable register remains.
class BrokenWriteMonitor(FakeMonitor):
    def set_volume(self, v):
        raise OSError('simulated persistent I2C failure')

broken = BrokenWriteMonitor()
mod.get_monitors = lambda: [broken]
res = mod.Hub._execute_action(dummy, 'set_volume', {'monitor_index': 0, 'value': 29})
assert res['write_ok'] is False and res['actual'] == 42 and 'persistent I2C' in res['retry_error']

mod.get_monitors = lambda: [fake]
res = mod.Hub._execute_action(dummy, 'toggle_mute', {'monitor_index': 0})
assert res['muted'] is True
res = mod.Hub._execute_action(dummy, 'toggle_mute', {'monitor_index': 0})
assert res['muted'] is False
res = mod.Hub._execute_action(dummy, 'switch_input', {'monitor_index': 0, 'value': 0x01})
assert res['actual'] == 0x01
print('OK: detection, brightness, volume, mute toggle, and input switching passed against fake monitor.')
