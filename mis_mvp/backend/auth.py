from __future__ import annotations

from hashlib import sha256, scrypt
from hmac import compare_digest
from os import urandom
from typing import Iterable

from .models import Role


PERMISSIONS: dict[Role, set[str]] = {
    Role.admin: {
        "machine:create",
        "machine:read",
        "machine:update",
        "machine:delete",
        "repair_order:create",
        "repair_order:update",
        "repair_order:assign",
        "repair_order:confirm",
        "repair_order:delete",
        "repair_order:engineer_close",
        "repair_order:read",
        "repair_sku:read",
        "repair_sku:write",
        "device_model:read",
        "device_model:write",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
        "warehouse:read",
        "warehouse:write",
        "warehouse:approve",
        "warehouse:issue",
        "warehouse:count",
        "warehouse:request",
        "sales_order:create",
        "sales_order:read",
        "payment:create",
        "payment:read",
        "purchase:create",
        "device:sell",
        "device:read",
        "repair:create",
        "repair:update",
        "repair:read",
        "customer:read",
        "customer:write",
        "settlement:create",
        "report:read",
        "audit:read",
    },
    Role.boss: {
        "machine:create",
        "machine:read",
        "machine:update",
        "machine:delete",
        "repair_order:create",
        "repair_order:update",
        "repair_order:assign",
        "repair_order:confirm",
        "repair_order:delete",
        "repair_order:engineer_close",
        "repair_order:read",
        "repair_sku:read",
        "repair_sku:write",
        "device_model:read",
        "device_model:write",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
        "warehouse:read",
        "warehouse:write",
        "warehouse:approve",
        "warehouse:issue",
        "warehouse:count",
        "warehouse:request",
        "sales_order:create",
        "sales_order:read",
        "payment:create",
        "payment:read",
        "purchase:create",
        "device:sell",
        "device:read",
        "repair:create",
        "repair:update",
        "repair:read",
        "customer:read",
        "customer:write",
        "settlement:create",
        "report:read",
        "audit:read",
    },
    Role.frontdesk: {
        "machine:create",
        "machine:read",
        "machine:update",
        "repair_order:create",
        "repair_order:update",
        "repair_order:assign",
        "repair_order:confirm",
        "repair_order:read",
        "repair_sku:read",
        "device_model:read",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
        "warehouse:read",
        "warehouse:request",
        "sales_order:create",
        "sales_order:read",
        "payment:create",
        "payment:read",
        "purchase:create",
        "device:sell",
        "device:read",
        "repair:read",
        "customer:read",
        "warehouse:read",
        "warehouse:request",
        "customer:write",
    },
    Role.engineer: {
        "machine:create",
        "machine:read",
        "machine:update",
        "repair_order:create",
        "repair_order:update",
        "repair_order:engineer_close",
        "repair_order:read",
        "repair_sku:read",
        "device_model:read",
        "customer:read",
        "warehouse:read",
        "warehouse:request",
    },
    Role.staff: {
        "machine:create",
        "machine:read",
        "machine:update",
        "repair_order:create",
        "repair_order:update",
        "repair_order:assign",
        "repair_order:confirm",
        "repair_order:delete",
        "repair_order:engineer_close",
        "repair_order:read",
        "repair_sku:read",
        "repair_sku:write",
        "device_model:read",
        "device_model:write",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
        "warehouse:read",
        "warehouse:write",
        "warehouse:approve",
        "warehouse:issue",
        "warehouse:count",
        "warehouse:request",
        "sales_order:create",
        "sales_order:read",
        "purchase:create",
        "device:sell",
        "device:read",
        "repair:create",
        "repair:update",
        "repair:read",
        "customer:read",
        "customer:write",
    },
    Role.finance: {
        "machine:read",
        "repair_order:read",
        "device_model:read",
        "recycle_order:read",
        "inventory:read",
        "warehouse:read",
        "sales_order:read",
        "payment:create",
        "payment:read",
        "device:read",
        "repair:read",
        "customer:read",
        "settlement:create",
        "report:read",
        "audit:read",
    },
}

# The catalog is deliberately code-owned: APIs cannot grant unknown permission names.
PERMISSION_CATALOG = {
    **{permission: "业务权限" for values in PERMISSIONS.values() for permission in values},
    "employee:read": "员工与账号", "employee:write": "员工与账号",
    "role:read": "角色与权限", "role:write": "角色与权限",
}
PERMISSIONS[Role.admin].update({"employee:read", "employee:write", "role:read", "role:write"})


def hash_password(password: str) -> str:
    """Password hashes written by new versions use a self-contained scrypt format."""
    salt = urandom(16)
    digest = scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """Return (valid, needs_upgrade), accepting legacy SHA-256 hashes once."""
    if stored.startswith("scrypt$"):
        try:
            _, n, r, p, salt, digest = stored.split("$", 5)
            candidate = scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest)))
            return compare_digest(candidate.hex(), digest), False
        except (ValueError, TypeError):
            return False, False
    return compare_digest(sha256(password.encode("utf-8")).hexdigest(), stored), True


def require_permission(role: Role, permission: str) -> None:
    if permission not in PERMISSIONS[role]:
        raise PermissionError(f"角色 {role.value} 无权执行 {permission}")


def permissions_for(role: Role) -> Iterable[str]:
    return sorted(PERMISSIONS[role])
