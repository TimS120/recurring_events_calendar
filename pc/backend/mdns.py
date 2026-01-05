from __future__ import annotations

import socket
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

from .config import API_PORT, INSTANCE_PREFIX, SERVICE_TYPE

zeroconf: Optional[Zeroconf] = None
service_info: Optional[ServiceInfo] = None
_mdns_enabled = True


def set_mdns_enabled(value: bool) -> None:
    global _mdns_enabled
    _mdns_enabled = bool(value)


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def register_mdns_service(server_id: str | None) -> None:
    global zeroconf, service_info
    if not _mdns_enabled:
        return
    try:
        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        hostname = socket.gethostname()
        instance_name = f"{INSTANCE_PREFIX}-{hostname}.{SERVICE_TYPE}"
        ip_address = socket.inet_aton(get_local_ip())
        properties = {
            b"path": b"/api",
            b"proto": b"1",
            b"server_id": (server_id or "").encode("utf-8"),
        }
        service_info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=instance_name,
            addresses=[ip_address],
            port=API_PORT,
            properties=properties,
        )
        zeroconf.register_service(service_info)
        print(f"[mDNS] Advertised {instance_name} on port {API_PORT}")
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(f"[mDNS] Registration failed: {exc!r}")
        traceback.print_exc()
        if zeroconf:
            zeroconf.close()
        zeroconf = None
        service_info = None


def unregister_mdns_service() -> None:
    global zeroconf, service_info
    if not _mdns_enabled:
        return
    if zeroconf:
        if service_info:
            zeroconf.unregister_service(service_info)
        zeroconf.close()
    zeroconf = None
    service_info = None
