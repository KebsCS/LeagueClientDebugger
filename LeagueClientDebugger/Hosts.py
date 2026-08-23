import os, platform, shutil


def get_hosts_path():
    if platform.system() == "Windows":
        return os.getenv("SystemRoot", r"C:\Windows") + r"\System32\drivers\etc\hosts"
    return "/etc/hosts"


def rewrite_etc_hosts(hostmap, save_code):
    hosts_file = get_hosts_path()
    backup_file = f'{hosts_file}.sbak'
    append = f'# LeagueClientDebugger-{save_code}'

    with open(hosts_file) as f:
        old_content = f.read()

    if old_content.strip() and not os.path.exists(backup_file):
        try:
            os.link(hosts_file, backup_file)
        except OSError:
            # File is locked, perform non-atomic copy
            shutil.copyfile(hosts_file, backup_file)

    temp = f"{hosts_file}.{save_code}.tmp"
    try:
        with open(temp, 'w') as f:
            for line in old_content.rstrip().split('\n'):
                if append in line:
                    continue
                f.write(f'{line}\n')

            for host, ip in sorted(hostmap.items()):
                f.write(f'{ip} {host:<30} {append}\n')
    except PermissionError:
        return False

    try:
        os.rename(temp, hosts_file)
    except OSError:
        # File is locked, perform non-atomic copy
        shutil.move(temp, hosts_file)

    return True
