"""Database seed utilities for RackDCIM Pro."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.device import DeviceCategory, DeviceModel, DeviceType, Manufacturer
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
    ("compute", "计算", "服务器/计算节点"),
    ("storage", "存储", "存储设备"),
    ("network", "网络", "交换机/路由等网络设备"),
    ("security", "安全", "防火墙/安全设备"),
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
        stmt = select(RackTemplate).where(RackTemplate.code == code, RackTemplate.deleted_at.is_(None))
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
        stmt = select(DeviceType).where(DeviceType.code == code, DeviceType.deleted_at.is_(None))
        if (await session.execute(stmt)).scalar_one_or_none():
            continue
        session.add(
            DeviceType(
                code=code,
                name=name,
                is_system=True,
                description=description,
            )
        )
    await session.commit()


async def seed_device_catalog(session: AsyncSession) -> None:
    for mfg_code, mfg_name, cat_code, cat_name, model_code, model_name, height_u, weight, power in DEFAULT_DEVICE_CATALOG:
        mfg_stmt = select(Manufacturer).where(
            Manufacturer.code == mfg_code, Manufacturer.deleted_at.is_(None)
        )
        manufacturer = (await session.execute(mfg_stmt)).scalar_one_or_none()
        if not manufacturer:
            manufacturer = Manufacturer(code=mfg_code, name=mfg_name)
            session.add(manufacturer)
            await session.flush()

        cat_stmt = select(DeviceCategory).where(
            DeviceCategory.code == cat_code, DeviceCategory.deleted_at.is_(None)
        )
        category = (await session.execute(cat_stmt)).scalar_one_or_none()
        if not category:
            category = DeviceCategory(code=cat_code, name=cat_name)
            session.add(category)
            await session.flush()

        model_stmt = select(DeviceModel).where(
            DeviceModel.code == model_code, DeviceModel.deleted_at.is_(None)
        )
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
