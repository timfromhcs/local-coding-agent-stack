import os

folders = ['scripts', '.', 'bin', r'C:\Users\hcsme\AppData\Local\Microsoft\WindowsApps']
for d in folders:
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        if f.startswith('hcscoder') and f.endswith('.cmd'):
            p = os.path.join(d, f)
            with open(p, 'rb') as fp:
                raw = fp.read()
            text = raw.decode('utf-8', errors='ignore')
            text = text.replace('\r\n', '\n').replace('\n', '\r\n')
            text = text.replace('::', 'REM ')
            text = text.replace('[✓]', '[+]').replace('âœ“', '+')
            with open(p, 'wb') as fp:
                fp.write(text.encode('ascii', errors='ignore'))
            print('Sanitized:', p)
