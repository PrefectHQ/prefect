import sys


def platform_is_linux() -> bool:
    return sys.platform.startswith("linux")


def get_docker_ip() -> str:
    """Get local docker internal IP without using shell=True in subprocess"""
    from subprocess import Popen, PIPE

    ip_route_proc = Popen(["ip", "route"], stdout=PIPE)
    grep_proc = Popen(["grep", "docker0"], stdin=ip_route_proc.stdout, stdout=PIPE)
    awk_proc = Popen(["awk", "{print $9}"], stdin=grep_proc.stdout, stdout=PIPE)
    return awk_proc.communicate()[0].strip().decode()
