from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.seed import seed_defaults
from app.models import (  # noqa: F401
    AuditLog,
    Building,
    DataCenter,
    Device,
    DeviceCategory,
    DeviceBmcProfile,
    DeviceContract,
    DeviceModel,
    DeviceParamProfile,
    DeviceSystemProfile,
    DeviceType,
    IpAddress,
    Floor,
    Manufacturer,
    Permission,
    Rack,
    RackPosition,
    RackTemplate,
    Role,
    RolePermission,
    Room,
    User,
    UserRole,
)
from app.models.base import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _ensure_sqlite_room_columns(connection) -> None:
    """Add room layout columns for existing SQLite databases (create_all does not alter)."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(room)")
    columns = {row[1] for row in result.fetchall()}
    alters = [
        ("rack_rows", "ALTER TABLE room ADD COLUMN rack_rows INTEGER NOT NULL DEFAULT 4"),
        ("rack_columns", "ALTER TABLE room ADD COLUMN rack_columns INTEGER NOT NULL DEFAULT 6"),
        ("row_layout", "ALTER TABLE room ADD COLUMN row_layout JSON"),
        ("code_mode", "ALTER TABLE room ADD COLUMN code_mode VARCHAR(20) NOT NULL DEFAULT 'auto'"),
        ("code_prefix", "ALTER TABLE room ADD COLUMN code_prefix VARCHAR(50)"),
        ("slot_codes", "ALTER TABLE room ADD COLUMN slot_codes JSON"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)


async def _ensure_sqlite_rack_code_unique_per_room(connection) -> None:
    """Migrate global rack.code uniqueness to (room_id, code) for SQLite."""
    if not str(settings.database_url).startswith("sqlite"):
        return

    result = await connection.exec_driver_sql("PRAGMA index_list(rack)")
    has_room_code = False
    has_code_only = False
    for row in result.fetchall():
        name, is_unique = row[1], row[2]
        if not is_unique:
            continue
        info = await connection.exec_driver_sql(f'PRAGMA index_info("{name}")')
        cols = [item[2] for item in info.fetchall()]
        if cols == ["room_id", "code"]:
            has_room_code = True
        if cols == ["code"]:
            has_code_only = True

    # Also rebuild when timestamp defaults were lost by a previous migration.
    needs_timestamp_defaults = False
    info = await connection.exec_driver_sql("PRAGMA table_info(rack)")
    for row in info.fetchall():
        # cid, name, type, notnull, dflt_value, pk
        if row[1] in {"created_at", "updated_at"} and row[4] is None:
            needs_timestamp_defaults = True
            break

    if has_room_code and not has_code_only and not needs_timestamp_defaults:
        return

    await _rebuild_sqlite_rack_table(connection)


async def _rebuild_sqlite_rack_table(connection) -> None:
    """Rebuild rack with room-scoped code unique + timestamp defaults."""
    await connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    await connection.exec_driver_sql(
        """
        CREATE TABLE rack_new (
            room_id CHAR(32) NOT NULL,
            rack_template_id CHAR(32),
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            row_no INTEGER NOT NULL,
            column_no INTEGER NOT NULL,
            total_u INTEGER NOT NULL,
            width INTEGER NOT NULL,
            depth INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL,
            description TEXT,
            id CHAR(32) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by CHAR(32),
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by CHAR(32),
            deleted_at DATETIME,
            deleted_by CHAR(32),
            version INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (id),
            CONSTRAINT uk_rack_room_code UNIQUE (room_id, code),
            CONSTRAINT uk_rack_room_name UNIQUE (room_id, name),
            FOREIGN KEY(room_id) REFERENCES room (id),
            FOREIGN KEY(rack_template_id) REFERENCES rack_template (id)
        )
        """
    )
    await connection.exec_driver_sql(
        """
        INSERT INTO rack_new (
            room_id, rack_template_id, code, name, row_no, column_no, total_u,
            width, depth, status, description, id, created_at, created_by,
            updated_at, updated_by, deleted_at, deleted_by, version
        )
        SELECT
            room_id, rack_template_id, code, name, row_no, column_no, total_u,
            width, depth, status, description, id,
            COALESCE(created_at, CURRENT_TIMESTAMP),
            created_by,
            COALESCE(updated_at, CURRENT_TIMESTAMP),
            updated_by, deleted_at, deleted_by, COALESCE(version, 1)
        FROM rack
        """
    )
    await connection.exec_driver_sql("DROP TABLE rack")
    await connection.exec_driver_sql("ALTER TABLE rack_new RENAME TO rack")
    await connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_rack_room_id ON rack (room_id)"
    )
    await connection.exec_driver_sql("PRAGMA foreign_keys=ON")


async def _ensure_sqlite_device_columns(connection) -> None:
    """Add device name/type/profile columns for existing SQLite databases."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(device)")
    columns = {row[1] for row in result.fetchall()}
    alters = [
        ("name", "ALTER TABLE device ADD COLUMN name VARCHAR(100)"),
        ("device_type_id", "ALTER TABLE device ADD COLUMN device_type_id CHAR(36)"),
        ("param_profile_id", "ALTER TABLE device ADD COLUMN param_profile_id CHAR(36)"),
        ("system_profile_id", "ALTER TABLE device ADD COLUMN system_profile_id CHAR(36)"),
        ("bmc_profile_id", "ALTER TABLE device ADD COLUMN bmc_profile_id CHAR(36)"),
        ("contract_id", "ALTER TABLE device ADD COLUMN contract_id CHAR(36)"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)


async def _ensure_sqlite_device_contract_columns(connection) -> None:
    """Patch device_contract: manual fields, nullable model id, price unit."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='device_contract'"
    )
    if not result.fetchone():
        return

    info = await connection.exec_driver_sql("PRAGMA table_info(device_contract)")
    rows = info.fetchall()
    columns = {row[1] for row in rows}
    model_id_notnull = False
    for row in rows:
        # cid, name, type, notnull, dflt_value, pk
        if row[1] == "device_model_id" and int(row[3] or 0) == 1:
            model_id_notnull = True

    alters = [
        ("device_name", "ALTER TABLE device_contract ADD COLUMN device_name VARCHAR(500) NOT NULL DEFAULT ''"),
        (
            "device_model_name",
            "ALTER TABLE device_contract ADD COLUMN device_model_name VARCHAR(500) NOT NULL DEFAULT ''",
        ),
        ("manufacturer_name", "ALTER TABLE device_contract ADD COLUMN manufacturer_name VARCHAR(100)"),
        (
            "price_unit",
            "ALTER TABLE device_contract ADD COLUMN price_unit VARCHAR(10) NOT NULL DEFAULT 'yuan'",
        ),
        ("device_names", "ALTER TABLE device_contract ADD COLUMN device_names JSON"),
        ("device_model_names", "ALTER TABLE device_contract ADD COLUMN device_model_names JSON"),
        ("manufacturer_names", "ALTER TABLE device_contract ADD COLUMN manufacturer_names JSON"),
        ("device_items", "ALTER TABLE device_contract ADD COLUMN device_items JSON"),
        ("contract_total", "ALTER TABLE device_contract ADD COLUMN contract_total NUMERIC(14, 2)"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)

    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET device_model_name = COALESCE(
            (SELECT name FROM device_model WHERE device_model.id = device_contract.device_model_id),
            device_model_name
        )
        WHERE device_model_name = '' AND device_model_id IS NOT NULL
        """
    )
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET manufacturer_name = (
            SELECT m.name FROM device_model dm
            JOIN manufacturer m ON m.id = dm.manufacturer_id
            WHERE dm.id = device_contract.device_model_id
        )
        WHERE manufacturer_name IS NULL AND device_model_id IS NOT NULL
        """
    )
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET device_name = device_model_name
        WHERE device_name = '' AND device_model_name != ''
        """
    )
    # 旧单值字段迁移为 JSON 数组
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET device_names = '["' || replace(device_name, '"', '') || '"]'
        WHERE (device_names IS NULL OR device_names = '' OR device_names = 'null')
          AND device_name != ''
        """
    )
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET device_model_names = '["' || replace(device_model_name, '"', '') || '"]'
        WHERE (device_model_names IS NULL OR device_model_names = '' OR device_model_names = 'null')
          AND device_model_name != ''
        """
    )
    # 合同级厂商迁移为与设备条目对齐的数组（按型号条数重复）
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET manufacturer_names = '["' || replace(manufacturer_name, '"', '') || '"]'
        WHERE (manufacturer_names IS NULL OR manufacturer_names = '' OR manufacturer_names = 'null')
          AND manufacturer_name IS NOT NULL AND manufacturer_name != ''
        """
    )
    # 旧合同总价：有单价与数量时回填 contract_total
    await connection.exec_driver_sql(
        """
        UPDATE device_contract
        SET contract_total = ROUND(unit_price * quantity, 2)
        WHERE contract_total IS NULL
          AND unit_price IS NOT NULL
          AND quantity > 0
        """
    )

    # SQLite cannot ALTER COLUMN nullability — rebuild when model id is still NOT NULL.
    if model_id_notnull:
        await _rebuild_sqlite_device_contract_table(connection)


async def _rebuild_sqlite_device_contract_table(connection) -> None:
    """Rebuild device_contract so device_model_id is nullable and price_unit exists."""
    await connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    await connection.exec_driver_sql(
        """
        CREATE TABLE device_contract_new (
            contract_no VARCHAR(100) NOT NULL,
            project_no VARCHAR(100),
            device_items JSON,
            device_names JSON,
            device_model_names JSON,
            manufacturer_names JSON,
            device_name VARCHAR(500) NOT NULL DEFAULT '',
            device_model_name VARCHAR(500) NOT NULL DEFAULT '',
            manufacturer_name VARCHAR(500),
            device_model_id CHAR(36),
            quantity INTEGER NOT NULL DEFAULT 0,
            unit_price NUMERIC(14, 2),
            contract_total NUMERIC(14, 2),
            price_unit VARCHAR(10) NOT NULL DEFAULT 'yuan',
            purchase_date DATE,
            description TEXT,
            id CHAR(36) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by CHAR(36),
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by CHAR(36),
            deleted_at DATETIME,
            deleted_by CHAR(36),
            version INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (id),
            CONSTRAINT uk_device_contract_no UNIQUE (contract_no),
            FOREIGN KEY(device_model_id) REFERENCES device_model (id)
        )
        """
    )
    info = await connection.exec_driver_sql("PRAGMA table_info(device_contract)")
    columns = {row[1] for row in info.fetchall()}
    has_price_unit = "price_unit" in columns
    has_names = "device_names" in columns
    has_models = "device_model_names" in columns
    has_mfgs = "manufacturer_names" in columns
    has_items = "device_items" in columns
    has_total = "contract_total" in columns
    price_unit_expr = "COALESCE(price_unit, 'yuan')" if has_price_unit else "'yuan'"
    names_expr = "device_names" if has_names else "NULL"
    models_expr = "device_model_names" if has_models else "NULL"
    mfgs_expr = "manufacturer_names" if has_mfgs else "NULL"
    items_expr = "device_items" if has_items else "NULL"
    total_expr = "contract_total" if has_total else "NULL"
    await connection.exec_driver_sql(
        f"""
        INSERT INTO device_contract_new (
            contract_no, project_no, device_items, device_names, device_model_names, manufacturer_names,
            device_name, device_model_name, manufacturer_name,
            device_model_id, quantity, unit_price, contract_total, price_unit, purchase_date, description,
            id, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, version
        )
        SELECT
            contract_no, project_no, {items_expr}, {names_expr}, {models_expr}, {mfgs_expr},
            COALESCE(device_name, ''),
            COALESCE(device_model_name, ''),
            manufacturer_name,
            device_model_id, quantity, unit_price, {total_expr}, {price_unit_expr}, purchase_date, description,
            id,
            COALESCE(created_at, CURRENT_TIMESTAMP), created_by,
            COALESCE(updated_at, CURRENT_TIMESTAMP), updated_by,
            deleted_at, deleted_by, COALESCE(version, 1)
        FROM device_contract
        """
    )
    await connection.exec_driver_sql("DROP TABLE device_contract")
    await connection.exec_driver_sql(
        "ALTER TABLE device_contract_new RENAME TO device_contract"
    )
    await connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_device_contract_device_model_id "
        "ON device_contract (device_model_id)"
    )
    await connection.exec_driver_sql("PRAGMA foreign_keys=ON")


async def _ensure_sqlite_ip_address_columns(connection) -> None:
    """Add network fields for existing SQLite ip_address tables."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ip_address'"
    )
    if not result.fetchone():
        return
    info = await connection.exec_driver_sql("PRAGMA table_info(ip_address)")
    columns = {row[1] for row in info.fetchall()}
    alters = [
        ("netmask", "ALTER TABLE ip_address ADD COLUMN netmask VARCHAR(64)"),
        ("gateway", "ALTER TABLE ip_address ADD COLUMN gateway VARCHAR(64)"),
        ("dns", "ALTER TABLE ip_address ADD COLUMN dns VARCHAR(64)"),
        ("dns_secondary", "ALTER TABLE ip_address ADD COLUMN dns_secondary VARCHAR(64)"),
        ("status", "ALTER TABLE ip_address ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'free'"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)
    await connection.exec_driver_sql(
        """
        UPDATE ip_address
        SET status = 'allocated'
        WHERE deleted_at IS NULL
          AND status = 'free'
          AND (
            device_id IS NOT NULL
            OR bind_type IN ('device', 'rack', 'rack_range')
          )
        """
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_room_columns(conn)
        await _ensure_sqlite_rack_code_unique_per_room(conn)
        await _ensure_sqlite_device_columns(conn)
        await _ensure_sqlite_device_contract_columns(conn)
        await _ensure_sqlite_ip_address_columns(conn)

    async with async_session_factory() as session:
        await seed_defaults(session)
        await _cleanup_orphan_racks(session)


async def _cleanup_orphan_racks(session: AsyncSession) -> None:
    """Soft-delete racks that still point at soft-deleted rooms (garbage leftovers)."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.infrastructure import Room
    from app.models.rack import Rack

    stmt = (
        select(Rack)
        .join(Room, Room.id == Rack.room_id)
        .where(Rack.deleted_at.is_(None), Room.deleted_at.is_not(None))
    )
    racks = list((await session.execute(stmt)).scalars().all())
    if not racks:
        return
    now = datetime.now(timezone.utc)
    for rack in racks:
        rack.deleted_at = now
    await session.commit()
