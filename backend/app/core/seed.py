"""Database seed utilities for RackDCIM Pro."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.device import Device, DeviceCategory, DeviceModel, DeviceType, Manufacturer
from app.models.rack import RackTemplate
from app.models.user import Permission, Role, RolePermission, User, UserRole, UserStatus

DEFAULT_PERMISSIONS = [
    ("admin:*", "Admin All", "Full system access"),
    ("datacenter:view", "View Data Centers", "View data center resources"),
    ("datacenter:create", "Create Data Centers", "Create data center resources"),
    ("datacenter:update", "Update Data Centers", "Update data center resources"),
    ("datacenter:delete", "Delete Data Centers", "Delete data center resources"),
    ("rack:view", "View Racks", "View rack resources"),
    ("rack:create", "Create Racks", "Create rack resources"),
    ("rack:update", "Update Racks", "Update rack resources"),
    ("rack:delete", "Delete Racks", "Delete rack resources"),
    ("device:view", "View Devices", "View device resources"),
    ("device:create", "Create Devices", "Create device resources"),
    ("device:update", "Update Devices", "Update and mount devices"),
    ("device:delete", "Delete Devices", "Delete device resources"),
    ("audit:view", "View Audit Logs", "View audit logs"),
    ("dashboard:view", "View Dashboard", "View dashboard statistics"),
    ("user:view", "View Users", "View user accounts"),
    ("user:create", "Create Users", "Create user accounts"),
    ("user:update", "Update Users", "Update user accounts"),
    ("user:delete", "Delete Users", "Delete user accounts"),
    ("role:view", "View Roles", "View roles and permissions"),
    ("role:create", "Create Roles", "Create roles"),
    ("role:update", "Update Roles", "Update roles"),
    ("role:delete", "Delete Roles", "Delete roles"),
    ("device:import", "Import Devices", "Import devices from Excel"),
    ("device:export", "Export Devices", "Export devices to Excel/PDF"),
    ("network:view", "View Network Design", "View network topology designs"),
    ("network:create", "Create Network Design", "Create network topology designs"),
    ("network:update", "Update Network Design", "Update network topology designs"),
    ("network:delete", "Delete Network Design", "Delete network topology designs"),
]

DEFAULT_DEVICE_CATALOG = [
    ("DELL", "Dell Technologies", "SERVER", "Server", "R750-2U", "PowerEdge R750", 2, 25.0, 750),
    ("HPE", "Hewlett Packard Enterprise", "SWITCH", "Network Switch", "SW-1U", "Switch 1U", 1, 5.0, 150),
]

DEFAULT_RACK_TEMPLATES = [
    ("STD-42U", "Standard 42U", 42, 600, 1000, "Standard 42U rack"),
    ("STD-48U", "Standard 48U", 48, 600, 1200, "Standard 48U rack"),
]

DEFAULT_DEVICE_TYPES = [
    ("compute", "计算服务器", "计算服务器/计算节点"),
    ("storage", "存储服务器", "存储服务器/存储设备"),
    ("switch_1g", "千兆交换机", "接入层千兆交换机（与万兆分属不同类型）"),
    ("switch_10g", "万兆交换机", "接入层万兆交换机（与千兆分属不同类型）"),
    ("switch_bmc_1g", "BMC千兆交换机", "带外/BMC 管理千兆交换机"),
    ("switch_ai", "AI交换机", "AI/智能网卡或 AI 网络交换机"),
    ("switch_agg", "汇聚交换机", "汇聚层交换机"),
    ("switch_core", "核心交换机", "核心层交换机"),
    ("gpu", "GPU", "GPU 加速卡/GPU 服务器"),
    ("router", "路由器", "路由器/网关"),
    ("security", "安全设备", "防火墙/安全设备"),
    ("other", "其他", "其他未分类设备"),
    ("network", "网络（通用）", "未细分的网络设备；新建设备请选用千兆/万兆等具体类型"),
]

DEFAULT_ADMIN = {
    "username": "admin",
    "password": "Admin@12345678",
    "email": "admin@rackdcim.example.com",
    "full_name": "System Administrator",
}


async def ensure_permissions(session: AsyncSession) -> None:
    stmt = select(Role).options(selectinload(Role.permissions)).where(
        Role.code == "admin", Role.deleted_at.is_(None)
    )
    admin_role = (await session.execute(stmt)).scalar_one_or_none()

    for code, name, description in DEFAULT_PERMISSIONS:
        perm_stmt = select(Permission).where(Permission.code == code, Permission.deleted_at.is_(None))
        permission = (await session.execute(perm_stmt)).scalar_one_or_none()
        if not permission:
            permission = Permission(code=code, name=name, description=description)
            session.add(permission)
            await session.flush()

        if admin_role:
            existing = {p.code for p in admin_role.permissions}
            if code not in existing:
                session.add(RolePermission(role_id=admin_role.id, permission_id=permission.id))

    await session.commit()


async def seed_rack_templates(session: AsyncSession) -> None:
    for code, name, total_u, width, depth, description in DEFAULT_RACK_TEMPLATES:
        stmt = select(RackTemplate).where(RackTemplate.code == code)
        if (await session.execute(stmt)).scalar_one_or_none():
            continue
        session.add(
            RackTemplate(
                code=code,
                name=name,
                total_u=total_u,
                width=width,
                depth=depth,
                description=description,
            )
        )
    await session.commit()


async def seed_device_types(session: AsyncSession) -> None:
    for code, name, description in DEFAULT_DEVICE_TYPES:
        stmt = select(DeviceType).where(DeviceType.code == code)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            # 同步预置名称/说明（兼容旧短名：计算/存储/安全）
            existing.name = name
            existing.description = description
            if existing.is_system is False and code in {
                "compute",
                "storage",
                "security",
                "other",
                "gpu",
                "switch_1g",
                "switch_10g",
                "switch_bmc_1g",
                "switch_ai",
                "switch_agg",
                "switch_core",
            }:
                existing.is_system = True
            continue
        session.add(
            DeviceType(
                code=code,
                name=name,
                is_system=True,
                description=description,
            )
        )
    await session.flush()
    await _reclassify_coarse_network_devices(session)
    await session.commit()


def _infer_device_type_code(text: str) -> str | None:
    import re

    raw = (text or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    compact = re.sub(r"[\s_\-/]+", "", lower)
    if re.search(r"安全|防火墙|firewall|waf", lower):
        return "security"
    if re.search(r"存储|storage|san|nas", lower):
        return "storage"
    if re.search(r"服务器|server|compute|host", lower) and not re.search(
        r"交换|switch", lower
    ):
        return "compute"
    if "核心" in raw and re.search(r"交换|switch", lower):
        return "switch_core"
    if "汇聚" in raw and re.search(r"交换|switch", lower):
        return "switch_agg"
    if re.search(r"路由|router", lower):
        return "router"
    if "万兆" in raw or re.search(r"10g|10ge|10gb|tengig|ten_gigabit", compact):
        return "switch_10g"
    if "千兆" in raw or re.search(r"千兆|1ge|gigabit", lower):
        return "switch_1g"
    return None


async def _reclassify_coarse_network_devices(session: AsyncSession) -> None:
    """将仍挂在「网络（通用）」的设备按名称细分为千兆/万兆等。"""
    types = (
        await session.execute(select(DeviceType).where(DeviceType.deleted_at.is_(None)))
    ).scalars().all()
    by_code = {t.code: t for t in types}
    network = by_code.get("network")
    if not network:
        return
    devices = (
        await session.execute(
            select(Device).where(
                Device.deleted_at.is_(None),
                Device.device_type_id == network.id,
            )
        )
    ).scalars().all()
    for device in devices:
        model_name = ""
        if device.model is not None:
            model_name = device.model.name or ""
        elif device.device_model_id:
            model = await session.get(DeviceModel, device.device_model_id)
            model_name = model.name if model else ""
        hay = f"{device.name or ''} {device.hostname or ''} {model_name}"
        inferred = _infer_device_type_code(hay)
        target = by_code.get(inferred or "")
        if target:
            device.device_type_id = target.id


async def seed_device_catalog(session: AsyncSession) -> None:
    for mfg_code, mfg_name, cat_code, cat_name, model_code, model_name, height_u, weight, power in DEFAULT_DEVICE_CATALOG:
        mfg_stmt = select(Manufacturer).where(Manufacturer.code == mfg_code)
        manufacturer = (await session.execute(mfg_stmt)).scalar_one_or_none()
        if not manufacturer:
            manufacturer = Manufacturer(code=mfg_code, name=mfg_name)
            session.add(manufacturer)
            await session.flush()

        cat_stmt = select(DeviceCategory).where(DeviceCategory.code == cat_code)
        category = (await session.execute(cat_stmt)).scalar_one_or_none()
        if not category:
            category = DeviceCategory(code=cat_code, name=cat_name)
            session.add(category)
            await session.flush()

        model_stmt = select(DeviceModel).where(DeviceModel.code == model_code)
        if (await session.execute(model_stmt)).scalar_one_or_none():
            continue
        session.add(
            DeviceModel(
                code=model_code,
                name=model_name,
                manufacturer_id=manufacturer.id,
                category_id=category.id,
                height_u=height_u,
                weight=weight,
                power=power,
            )
        )
    await session.commit()


async def seed_defaults(session: AsyncSession) -> None:
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        await ensure_permissions(session)
        await seed_rack_templates(session)
        await seed_device_types(session)
        await seed_device_catalog(session)
        return

    permissions: dict[str, Permission] = {}
    for code, name, description in DEFAULT_PERMISSIONS:
        permission = Permission(code=code, name=name, description=description)
        session.add(permission)
        permissions[code] = permission
    await session.flush()

    admin_role = Role(code="admin", name="Administrator", description="System administrator")
    session.add(admin_role)
    await session.flush()

    for permission in permissions.values():
        session.add(RolePermission(role_id=admin_role.id, permission_id=permission.id))

    admin_user = User(
        username=DEFAULT_ADMIN["username"],
        password_hash=hash_password(DEFAULT_ADMIN["password"]),
        email=DEFAULT_ADMIN["email"],
        full_name=DEFAULT_ADMIN["full_name"],
        status=UserStatus.ACTIVE,
    )
    session.add(admin_user)
    await session.flush()

    session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    await session.commit()

    await seed_rack_templates(session)
    await seed_device_types(session)
    await seed_device_catalog(session)
