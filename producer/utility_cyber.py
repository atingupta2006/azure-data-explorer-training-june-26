"""Utility cyber security event templates — default scenario for ADX training."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

JSON_TEMPLATES: list[dict[str, Any]] = [
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.1.44",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "operator@utility.com",
        "Severity": "High",
        "Message": "Failed login after 3 attempts",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.1.88",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "contractor@utility.com",
        "Severity": "High",
        "Message": "Invalid password",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.2.10",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "unknown",
        "Severity": "Critical",
        "Message": "Brute force pattern detected",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "AuthSuccess",
        "SourceIP": "10.20.1.12",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "operator@utility.com",
        "Severity": "Low",
        "Message": "Login successful",
        "Facility": "Substation-A",
    },
    {
        "EventType": "AuthSuccess",
        "SourceIP": "10.20.1.15",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "supervisor@utility.com",
        "Severity": "Low",
        "Message": "Login successful",
        "Facility": "Substation-A",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.10",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked inbound scan",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.11",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked port sweep",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.3.20",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "field@utility.com",
        "Severity": "Low",
        "Message": "VPN session started",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.3.21",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "auditor@utility.com",
        "Severity": "Medium",
        "Message": "VPN session started",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "ConfigChange",
        "SourceIP": "10.20.4.5",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "admin@utility.com",
        "Severity": "Medium",
        "Message": "Firewall rule updated",
        "Facility": "Substation-B",
    },
    {
        "EventType": "FirewallAllow",
        "SourceIP": "10.20.6.10",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "Low",
        "Message": "Allowed outbound HTTPS",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "PrivilegeEscalation",
        "SourceIP": "10.20.6.11",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "admin@utility.com",
        "Severity": "Critical",
        "Message": "Role elevation detected",
        "Facility": "SCADA-Gateway",
    },
]

# Locked course counts — must match tools/profiles/lab.yaml
JSON_EVENT_COUNTS: dict[str, int] = {
    "AuthFailure": 300,
    "AuthSuccess": 200,
    "FirewallDeny": 400,
    "FirewallAllow": 200,
    "VPNLogin": 200,
    "ConfigChange": 100,
    "PrivilegeEscalation": 100,
}

CSV_EVENT_COUNTS: dict[str, int] = {
    "AuthFailure": 200,
    "AuthSuccess": 100,
    "FirewallDeny": 200,
    "FirewallAllow": 100,
    "VPNLogin": 100,
    "VPNLogout": 100,
    "PrivilegeEscalation": 100,
    "ConfigChange": 100,
}

EVENTHUB_EVENT_COUNTS: dict[str, int] = {
    "AuthFailure": 200,
    "FirewallDeny": 100,
    "VPNLogin": 200,
}

PRACTICE_EVENT_COUNTS: dict[str, int] = {
    "AuthFailure": 400,
    "FirewallDeny": 500,
    "AuthSuccess": 185,
    "FirewallAllow": 183,
    "VPNLogin": 183,
    "VPNLogout": 183,
    "ConfigChange": 183,
    "PrivilegeEscalation": 183,
}

CSV_TEMPLATES: list[tuple[str, str, str, str, str, str]] = [
    ("AuthFailure", "10.20.5.10", "operator@utility.com", "High", "Web login failed", "Substation-A"),
    ("AuthFailure", "10.20.5.11", "unknown", "Critical", "Brute force on web portal", "Corporate-VPN"),
    ("FirewallDeny", "203.0.113.50", "", "High", "Blocked web exploit attempt", "DMZ-Firewall"),
    ("FirewallAllow", "10.20.5.20", "", "Low", "Allowed outbound HTTPS", "DMZ-Firewall"),
    ("VPNLogin", "10.20.5.30", "contractor@utility.com", "Low", "VPN via web gateway", "Corporate-VPN"),
    ("VPNLogout", "10.20.5.31", "contractor@utility.com", "Low", "VPN session ended", "Corporate-VPN"),
    ("AuthSuccess", "10.20.5.12", "supervisor@utility.com", "Low", "Web login OK", "Substation-A"),
    ("PrivilegeEscalation", "10.20.5.13", "admin@utility.com", "Critical", "Role elevation on web portal", "SCADA-Gateway"),
    ("ConfigChange", "10.20.5.14", "admin@utility.com", "Medium", "Web ACL updated", "Substation-B"),
]

EVENTHUB_TEMPLATES: list[dict[str, Any]] = [
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.8.1",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "field@utility.com",
        "Severity": "High",
        "Message": "Streaming auth failure",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "AuthFailure",
        "SourceIP": "10.20.8.2",
        "DestinationHost": "scada-gw.utility.local",
        "UserPrincipal": "unknown",
        "Severity": "Critical",
        "Message": "Invalid token in stream",
        "Facility": "Substation-A",
    },
    {
        "EventType": "FirewallDeny",
        "SourceIP": "203.0.113.80",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Streaming deny rule triggered",
        "Facility": "DMZ-Firewall",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.8.5",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "contractor@utility.com",
        "Severity": "Low",
        "Message": "VPN session started via stream",
        "Facility": "Corporate-VPN",
    },
    {
        "EventType": "VPNLogin",
        "SourceIP": "10.20.8.6",
        "DestinationHost": "vpn.utility.local",
        "UserPrincipal": "auditor@utility.com",
        "Severity": "Medium",
        "Message": "VPN session started via stream",
        "Facility": "Corporate-VPN",
    },
]

IOT_TEMPLATES: list[dict[str, Any]] = [
    {
        "deviceId": "substation-sensor-01",
        "EventType": "SensorAnomaly",
        "SourceIP": "10.20.9.1",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Temperature spike near access panel",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-02",
        "EventType": "DeviceHeartbeat",
        "SourceIP": "10.20.9.2",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "Low",
        "Message": "Device online",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-01",
        "EventType": "ConfigChange",
        "SourceIP": "10.20.9.1",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "iot-admin@utility.com",
        "Severity": "Medium",
        "Message": "Firmware config push acknowledged",
        "Facility": "Substation-C",
    },
    {
        "deviceId": "substation-sensor-03",
        "EventType": "SensorAnomaly",
        "SourceIP": "10.20.9.3",
        "DestinationHost": "iot-gateway.utility.local",
        "UserPrincipal": "",
        "Severity": "Critical",
        "Message": "Vibration pattern outside baseline",
        "Facility": "Substation-D",
    },
    {
        "deviceId": "substation-sensor-02",
        "EventType": "FirewallDeny",
        "SourceIP": "10.20.9.2",
        "DestinationHost": "dmz.utility.local",
        "UserPrincipal": "",
        "Severity": "High",
        "Message": "Blocked outbound connection from IoT gateway",
        "Facility": "DMZ-Firewall",
    },
]

CSV_HEADER = [
    "Timestamp",
    "EventType",
    "SourceIP",
    "DestinationHost",
    "UserPrincipal",
    "Severity",
    "Message",
    "Facility",
]

DEFAULT_BASE = datetime(2026, 6, 11, 9, 0, 0, tzinfo=timezone.utc)

# IPs in ThreatIntelRef (Day 4) — preserved by producer (not varied)
PINNED_SOURCE_IPS: frozenset[str] = frozenset(
    {
        "10.20.1.44",
        "203.0.113.50",
        "203.0.113.80",
        "10.20.8.1",
        "10.20.9.3",
    }
)
