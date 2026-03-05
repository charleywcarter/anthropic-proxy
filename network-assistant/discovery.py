"""
Network topology discovery engine.

Logs into seed devices via SSH, runs CDP/LLDP commands, discovers neighbors,
and recursively crawls the network to build a full topology graph.
"""

import ipaddress
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from parsers import (
    parse_cdp_neighbors_detail,
    parse_hostname,
    parse_lldp_neighbors_detail,
    parse_version_brief,
)

logger = logging.getLogger("discovery")


class Device:
    """Represents a discovered network device."""

    def __init__(self, ip, hostname=None):
        self.ip = ip
        self.hostname = hostname or ip
        self.platform = ""
        self.software = ""
        self.serial = ""
        self.capabilities = ""
        self.device_type = "cisco_ios"
        self.neighbors = []  # list of Link objects
        self.polled = False
        self.error = None

    def to_dict(self):
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "platform": self.platform,
            "software": self.software,
            "serial": self.serial,
            "capabilities": self.capabilities,
            "polled": self.polled,
            "error": self.error,
        }


class Link:
    """Represents a link between two devices."""

    def __init__(
        self,
        local_device,
        local_interface,
        remote_device,
        remote_interface,
        protocol="cdp",
    ):
        self.local_device = local_device
        self.local_interface = local_interface
        self.remote_device = remote_device
        self.remote_interface = remote_interface
        self.protocol = protocol

    def to_dict(self):
        return {
            "local_device": self.local_device,
            "local_interface": self.local_interface,
            "remote_device": self.remote_device,
            "remote_interface": self.remote_interface,
            "protocol": self.protocol,
        }


class TopologyDiscovery:
    """Discovers network topology using CDP/LLDP."""

    def __init__(self, config):
        self.config = config
        defaults = config.get("defaults", {})
        self.default_username = defaults.get("username", "admin")
        self.default_password = defaults.get("password", "")
        self.default_secret = defaults.get("secret", "")
        self.default_device_type = defaults.get("device_type", "cisco_ios")
        self.default_timeout = defaults.get("timeout", 30)
        self.default_key_file = defaults.get("key_file")

        disc = config.get("discovery", {})
        self.max_hops = disc.get("max_hops", 10)
        self.protocols = disc.get("protocols", ["cdp", "lldp"])
        self.allowed_prefixes = [
            ipaddress.ip_network(p, strict=False)
            for p in disc.get("allowed_prefixes", [])
        ]
        self.excluded_ips = set(disc.get("excluded_ips", []))
        self.max_workers = disc.get("max_workers", 5)

        # Discovered topology state
        self.devices = OrderedDict()  # ip -> Device
        self.links = []  # list of Link
        self._lock = threading.Lock()
        self._progress_callbacks = []

    def on_progress(self, callback):
        """Register a callback: callback(message, devices_dict, links_list)"""
        self._progress_callbacks.append(callback)

    def _notify(self, message):
        logger.info(message)
        for cb in self._progress_callbacks:
            try:
                cb(message, self.get_topology())
            except Exception:
                pass

    def _is_ip_allowed(self, ip):
        if not ip:
            return False
        if ip in self.excluded_ips:
            return False
        if not self.allowed_prefixes:
            return True
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in self.allowed_prefixes)

    def _connect(self, device):
        """Create an SSH connection to a device."""
        # Find seed config for per-device overrides
        seed_cfg = {}
        for s in self.config.get("seed_devices", []):
            if s.get("host") == device.ip:
                seed_cfg = s
                break

        params = {
            "device_type": seed_cfg.get("device_type", self.default_device_type),
            "host": device.ip,
            "username": seed_cfg.get("username", self.default_username),
            "password": seed_cfg.get("password", self.default_password),
            "secret": seed_cfg.get("secret", self.default_secret),
            "timeout": self.default_timeout,
            "conn_timeout": self.default_timeout,
        }
        key_file = seed_cfg.get("key_file", self.default_key_file)
        if key_file:
            params["use_keys"] = True
            params["key_file"] = key_file

        device.device_type = params["device_type"]
        return ConnectHandler(**params)

    def _poll_device(self, device):
        """SSH into a device, gather info, and return discovered neighbors."""
        self._notify(f"Connecting to {device.ip} ...")
        try:
            conn = self._connect(device)
        except NetmikoAuthenticationException:
            device.error = "Authentication failed"
            device.polled = True
            self._notify(f"Auth failed for {device.ip}")
            return []
        except NetmikoTimeoutException:
            device.error = "Connection timed out"
            device.polled = True
            self._notify(f"Timeout connecting to {device.ip}")
            return []
        except Exception as e:
            device.error = str(e)
            device.polled = True
            self._notify(f"Error connecting to {device.ip}: {e}")
            return []

        try:
            # Enter enable mode if needed
            if device.device_type in ("cisco_ios", "cisco_xe", "cisco_nxos"):
                try:
                    conn.enable()
                except Exception:
                    pass  # may already be in enable

            # Get hostname
            out = conn.send_command("show run | include hostname")
            hostname = parse_hostname(out)
            if hostname:
                device.hostname = hostname

            # Get version info
            out = conn.send_command("show version")
            info = parse_version_brief(out)
            device.platform = info["platform"]
            device.software = info["software"]
            device.serial = info["serial"]

            # Discover neighbors
            raw_neighbors = []
            if "cdp" in self.protocols:
                try:
                    out = conn.send_command("show cdp neighbors detail")
                    raw_neighbors.extend(parse_cdp_neighbors_detail(out))
                except Exception as e:
                    logger.warning(f"CDP failed on {device.ip}: {e}")

            if "lldp" in self.protocols:
                try:
                    out = conn.send_command("show lldp neighbors detail")
                    raw_neighbors.extend(parse_lldp_neighbors_detail(out))
                except Exception as e:
                    logger.warning(f"LLDP failed on {device.ip}: {e}")

            device.polled = True
            conn.disconnect()

            self._notify(
                f"Polled {device.hostname} ({device.ip}) — "
                f"{len(raw_neighbors)} neighbor(s)"
            )
            return raw_neighbors

        except Exception as e:
            device.error = str(e)
            device.polled = True
            try:
                conn.disconnect()
            except Exception:
                pass
            self._notify(f"Error polling {device.ip}: {e}")
            return []

    def _get_or_create_device(self, ip, hostname=None):
        """Thread-safe device lookup/creation."""
        with self._lock:
            if ip not in self.devices:
                self.devices[ip] = Device(ip, hostname)
            elif hostname and self.devices[ip].hostname == ip:
                self.devices[ip].hostname = hostname
            return self.devices[ip]

    def _add_link(self, link):
        """Thread-safe link addition, deduplicating bidirectional links."""
        with self._lock:
            for existing in self.links:
                if (
                    existing.local_device == link.remote_device
                    and existing.remote_device == link.local_device
                    and existing.local_interface == link.remote_interface
                    and existing.remote_interface == link.local_interface
                ):
                    return  # reverse link already exists
                if (
                    existing.local_device == link.local_device
                    and existing.remote_device == link.remote_device
                    and existing.local_interface == link.local_interface
                    and existing.remote_interface == link.remote_interface
                ):
                    return  # duplicate
            self.links.append(link)

    def discover(self):
        """Run the full topology discovery. Returns (devices, links)."""
        self.devices.clear()
        self.links.clear()

        # Seed the initial devices
        seeds = self.config.get("seed_devices", [])
        if not seeds:
            self._notify("No seed devices configured!")
            return self.get_topology()

        queue = []  # (device, hop_count)
        for seed in seeds:
            ip = seed["host"]
            dev = self._get_or_create_device(ip)
            queue.append((dev, 0))

        self._notify(f"Starting discovery with {len(queue)} seed device(s)")

        # BFS with thread pool
        visited = set()
        while queue:
            # Group current batch
            batch = []
            next_queue = []
            for dev, hops in queue:
                if dev.ip in visited:
                    continue
                if hops > self.max_hops:
                    continue
                if not self._is_ip_allowed(dev.ip):
                    continue
                visited.add(dev.ip)
                batch.append((dev, hops))

            if not batch:
                break

            # Poll batch in parallel
            futures = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                for dev, hops in batch:
                    fut = pool.submit(self._poll_device, dev)
                    futures[fut] = (dev, hops)

                for fut in as_completed(futures):
                    dev, hops = futures[fut]
                    try:
                        raw_neighbors = fut.result()
                    except Exception as e:
                        logger.error(f"Unexpected error polling {dev.ip}: {e}")
                        continue

                    for nb in raw_neighbors:
                        nb_ip = nb.get("ip_address", "")
                        nb_hostname = nb.get("device_id", "")

                        if not nb_ip and not nb_hostname:
                            continue

                        # Create or get neighbor device
                        if nb_ip:
                            nb_dev = self._get_or_create_device(nb_ip, nb_hostname)
                        else:
                            # No IP — use hostname as key
                            nb_dev = self._get_or_create_device(
                                nb_hostname, nb_hostname
                            )

                        # Record link
                        link = Link(
                            local_device=dev.hostname,
                            local_interface=nb.get("local_interface", ""),
                            remote_device=nb_dev.hostname,
                            remote_interface=nb.get("remote_interface", ""),
                            protocol=nb.get("protocol", "cdp"),
                        )
                        self._add_link(link)

                        if nb_dev.capabilities:
                            pass
                        else:
                            nb_dev.capabilities = nb.get("capabilities", "")
                        if nb.get("platform"):
                            nb_dev.platform = nb_dev.platform or nb["platform"]

                        # Queue neighbor for crawling if not yet visited
                        if nb_ip and nb_ip not in visited:
                            next_queue.append((nb_dev, hops + 1))

            queue = next_queue

        self._notify(
            f"Discovery complete: {len(self.devices)} device(s), "
            f"{len(self.links)} link(s)"
        )
        return self.get_topology()

    def get_topology(self):
        """Return serializable topology data."""
        with self._lock:
            return {
                "devices": {
                    ip: dev.to_dict() for ip, dev in self.devices.items()
                },
                "links": [link.to_dict() for link in self.links],
            }
