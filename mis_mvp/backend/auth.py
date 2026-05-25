from __future__ import annotations

from hashlib import sha256
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
        "repair_order:read",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
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
    Role.staff: {
        "machine:create",
        "machine:read",
        "machine:update",
        "repair_order:create",
        "repair_order:update",
        "repair_order:read",
        "recycle_order:create",
        "recycle_order:update",
        "recycle_order:read",
        "inventory:read",
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
        "recycle_order:read",
        "inventory:read",
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


def hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def require_permission(role: Role, permission: str) -> None:
    if permission not in PERMISSIONS[role]:
        raise PermissionError(f"角色 {role.value} 无权执行 {permission}")


def permissions_for(role: Role) -> Iterable[str]:
    return sorted(PERMISSIONS[role])
