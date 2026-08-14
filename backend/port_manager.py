"""Port allocation within the configured range, avoiding in-use ports."""

import docker

from config import PORT_RANGE
from database import SessionLocal
from models import Lease


def allocate_port():
    """Return the first free port in PORT_RANGE.

    A port is considered free if it is not held by a running lease in the
    database and not currently bound by a Docker container. Raises RuntimeError
    if no port is available.
    """
    # Ports reserved by running leases in the database.
    db = SessionLocal()
    try:
        reserved = {
            lease.port
            for lease in db.query(Lease).filter(Lease.status == "running").all()
        }
    finally:
        db.close()

    # Ports actually bound by Docker containers right now.
    docker_client = docker.from_env()
    docker_ports = set()
    try:
        for container in docker_client.containers.list():
            bindings = (container.attrs.get("HostConfig") or {}).get("PortBindings") or {}
            for binding in bindings.values():
                for entry in binding:
                    host_port = entry.get("HostPort")
                    if host_port:
                        docker_ports.add(int(host_port))
    except Exception:
        # If Docker is unreachable, fall back to DB-only accounting.
        pass

    used = reserved | docker_ports

    for port in range(PORT_RANGE[0], PORT_RANGE[1] + 1):
        if port not in used:
            return port

    raise RuntimeError("No available ports in range")
