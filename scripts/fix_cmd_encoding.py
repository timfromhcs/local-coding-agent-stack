import os

folders = ['scripts', '.', 'bin', r'C:\Users\hcsme\AppData\Local\Microsoft\WindowsApps']
for d in folders:
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        if (f.startswith('hcscoder') and (f.endswith('.cmd') or f.endswith('.ps1'))) or f == 'install.ps1':
            p = os.path.join(d, f)
            with open(p, 'rb') as fp:
                raw = fp.read()
            text = raw.decode('utf-8', errors='ignore')
            text = text.replace('\r\n', '\n').replace('\n', '\r\n')
            if f.endswith('.cmd'):
                text = text.replace('::', 'REM ')
            text = text.replace('[✓]', '[+]').replace('âœ“', '+').replace('✓', '+').replace('—', '-')
            # Ensure pure ascii
            ascii_bytes = text.encode('ascii', errors='ignore')
            with open(p, 'wb') as fp:
                fp.write(ascii_bytes)
            print('Sanitized:', p)
