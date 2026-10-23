#!/usr/bin/python3 -I
"""Apply one fan request without disabling the kernel thermal governor."""
import json
from pathlib import Path
import sys


def main():
    request = json.loads(sys.stdin.readline())['mode']
    if request not in ('ON', 'OFF'):
        raise ValueError('Choose ON or OFF')
    hwmon = next(p for p in Path('/sys/class/hwmon').glob('hwmon*')
                 if (p / 'name').read_text().strip() == 'pwmfan')
    pwm = hwmon / 'pwm1'
    temperature = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
    message = ''
    if request == 'OFF' and temperature >= 65:
        message = f'Automatic cooling: {temperature:.1f} °C'
    else:
        pwm.write_text('255' if request == 'ON' else '0')
    # The thermal governor may change this setting again at any time.
    mode = 'ON' if int(pwm.read_text()) > 0 else 'OFF'
    print(json.dumps({'mode': mode, 'rpm': int((hwmon / 'fan1_input').read_text()),
                      'message': message}), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('No command-line arguments are supported')
    main()
