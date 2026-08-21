from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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
    NetworkLink,
    NetworkNode,
    NetworkProject,
    NetworkTopology,
    NetworkLabSession,
    NetworkDesignModel,
    NetworkModelFolder,
    NetworkWiringRule,
    Floor,
    Manufacturer,
    Permission,
    PersonnelInternal,
    PersonnelOrgChart,
    PersonnelOrgLink,
    PersonnelOrgNode,
    PersonnelSupplier,
    PersonnelSupplierContract,
    PersonnelSupplierProduct,
    Rack,
    RackPosition,
    RackTemplate,
    Role,
    RolePermission,
    Room,
    User,
    UserRole,
    Warehouse,
    WarehouseAsset,
)
from app.models.base import Base

settings = get_settings()

_IS_SQLITE = str(settings.database_url).startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.debug}
if _IS_SQLITE:
    # WAL + busy_timeout：降低 “database is locked”（大画布保存 / 并发请求）
    _engine_kwargs["connect_args"] = {
        "timeout": 60.0,
        "check_same_thread": False,
    }
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


if _IS_SQLITE:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_on_connect(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
        ("pillar_layout", "ALTER TABLE room ADD COLUMN pillar_layout JSON"),
        ("purpose", "ALTER TABLE room ADD COLUMN purpose VARCHAR(50) DEFAULT 'production'"),
        ("importance", "ALTER TABLE room ADD COLUMN importance VARCHAR(20) DEFAULT 'medium'"),
        ("code", "ALTER TABLE room ADD COLUMN code VARCHAR(50) NOT NULL DEFAULT ''"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)
            columns.add(col)
    if "code" in columns:
        await _backfill_sqlite_room_cr_codes(connection)
        # Ensure unique index for room.code when possible
        idx = await connection.exec_driver_sql("PRAGMA index_list(room)")
        has_uk = False
        for item in idx.fetchall():
            if item[1] == "uk_room_code":
                has_uk = True
                break
        if not has_uk:
            try:
                await connection.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uk_room_code ON room (code)"
                )
            except Exception:
                pass


async def _backfill_sqlite_room_cr_codes(connection) -> None:
    """Assign CR1、CR2… to rooms missing a CR* business code (empty / legacy RM-*)."""
    import re

    rows = await connection.exec_driver_sql(
        "SELECT id, code FROM room WHERE deleted_at IS NULL ORDER BY created_at ASC, name ASC"
    )
    rooms = rows.fetchall()
    if not rooms:
        return

    cr_re = re.compile(r"^CR(\d+)$", re.IGNORECASE)
    used: set[str] = set()
    max_n = 0
    need_ids: list[str] = []
    for rid, code in rooms:
        raw = str(code or "").strip().upper()
        m = cr_re.match(raw)
        if m:
            used.add(raw)
            max_n = max(max_n, int(m.group(1)))
        else:
            # 空编号或旧版 RM-xxxx / 非 CR 编号，统一改成 CR 顺序号
            need_ids.append(str(rid))

    for rid in need_ids:
        max_n += 1
        code = f"CR{max_n}"
        while code in used:
            max_n += 1
            code = f"CR{max_n}"
        used.add(code)
        await connection.exec_driver_sql(
            "UPDATE room SET code = ? WHERE id = ?",
            (code, rid),
        )


async def _ensure_sqlite_rack_columns(connection) -> None:
    """Add rack usage/color columns for existing SQLite databases."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(rack)")
    columns = {row[1] for row in result.fetchall()}
    alters = [
        ("app_usage", "ALTER TABLE rack ADD COLUMN app_usage VARCHAR(100)"),
        ("app_color", "ALTER TABLE rack ADD COLUMN app_color VARCHAR(20)"),
        ("seq_no", "ALTER TABLE rack ADD COLUMN seq_no INTEGER"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)
            columns.add(col)
    if "seq_no" in columns:
        # Backfill sequential numbers per room by row/column order when missing
        rooms = await connection.exec_driver_sql(
            "SELECT DISTINCT room_id FROM rack WHERE deleted_at IS NULL"
        )
        for room_row in rooms.fetchall():
            room_id = room_row[0]
            racks = await connection.exec_driver_sql(
                "SELECT id FROM rack WHERE room_id = ? AND deleted_at IS NULL "
                "ORDER BY row_no ASC, column_no ASC, code ASC",
                (room_id,),
            )
            seq = 0
            for rack_row in racks.fetchall():
                seq += 1
                await connection.exec_driver_sql(
                    "UPDATE rack SET seq_no = ? WHERE id = ? AND (seq_no IS NULL OR seq_no = 0)",
                    (seq, rack_row[0]),
                )
        try:
            await connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_rack_room_seq_no ON rack (room_id, seq_no)"
            )
        except Exception:
            pass


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
        (
            "network_panel_bound",
            "ALTER TABLE device ADD COLUMN network_panel_bound BOOLEAN NOT NULL DEFAULT 0",
        ),
        ("manufacturer_id", "ALTER TABLE device ADD COLUMN manufacturer_id CHAR(36)"),
        ("project_scope", "ALTER TABLE device ADD COLUMN project_scope VARCHAR(200)"),
        ("project_app", "ALTER TABLE device ADD COLUMN project_app VARCHAR(200)"),
        ("warranty_years", "ALTER TABLE device ADD COLUMN warranty_years INTEGER"),
        ("mounted_at", "ALTER TABLE device ADD COLUMN mounted_at DATETIME"),
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
        ("project_budget", "ALTER TABLE device_contract ADD COLUMN project_budget NUMERIC(14, 2)"),
        ("purchase_org", "ALTER TABLE device_contract ADD COLUMN purchase_org VARCHAR(200)"),
        ("fund_source", "ALTER TABLE device_contract ADD COLUMN fund_source VARCHAR(100)"),
        ("using_org", "ALTER TABLE device_contract ADD COLUMN using_org VARCHAR(100)"),
        ("winning_bidder", "ALTER TABLE device_contract ADD COLUMN winning_bidder VARCHAR(200)"),
        ("signed_at", "ALTER TABLE device_contract ADD COLUMN signed_at DATE"),
        ("archived_at", "ALTER TABLE device_contract ADD COLUMN archived_at DATETIME"),
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
        ("segment_id", "ALTER TABLE ip_address ADD COLUMN segment_id CHAR(36)"),
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


async def _ensure_sqlite_ip_segment(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ip_segment'"
    )
    if not result.fetchone():
        await connection.exec_driver_sql(
            """
            CREATE TABLE ip_segment (
                application VARCHAR(100),
                network VARCHAR(64) NOT NULL DEFAULT '',
                prefix_len INTEGER NOT NULL DEFAULT 24,
                gateway VARCHAR(64),
                address_purpose VARCHAR(50),
                network_type VARCHAR(50),
                location VARCHAR(100),
                remarks TEXT,
                name VARCHAR(100) NOT NULL,
                start_ip VARCHAR(64) NOT NULL,
                end_ip VARCHAR(64) NOT NULL,
                netmask VARCHAR(64),
                dns VARCHAR(64),
                dns_secondary VARCHAR(64),
                application_type VARCHAR(50),
                label VARCHAR(100),
                description TEXT,
                id CHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                created_by CHAR(36),
                updated_at DATETIME NOT NULL,
                updated_by CHAR(36),
                deleted_at DATETIME,
                deleted_by CHAR(36),
                version INTEGER NOT NULL,
                PRIMARY KEY (id)
            )
            """
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ip_segment_start_ip ON ip_segment (start_ip)"
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ip_segment_end_ip ON ip_segment (end_ip)"
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ip_segment_application_type ON ip_segment (application_type)"
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_ip_segment_network ON ip_segment (network)"
        )
        return

    info = await connection.exec_driver_sql("PRAGMA table_info(ip_segment)")
    columns = {row[1] for row in info.fetchall()}
    alters = [
        ("application", "ALTER TABLE ip_segment ADD COLUMN application VARCHAR(100)"),
        ("network", "ALTER TABLE ip_segment ADD COLUMN network VARCHAR(64) DEFAULT ''"),
        ("prefix_len", "ALTER TABLE ip_segment ADD COLUMN prefix_len INTEGER DEFAULT 24"),
        ("address_purpose", "ALTER TABLE ip_segment ADD COLUMN address_purpose VARCHAR(50)"),
        ("network_type", "ALTER TABLE ip_segment ADD COLUMN network_type VARCHAR(50)"),
        ("location", "ALTER TABLE ip_segment ADD COLUMN location VARCHAR(100)"),
        ("remarks", "ALTER TABLE ip_segment ADD COLUMN remarks TEXT"),
    ]
    for col, sql in alters:
        if col not in columns:
            await connection.exec_driver_sql(sql)
    await connection.exec_driver_sql(
        """
        UPDATE ip_segment
        SET network = COALESCE(NULLIF(network, ''), start_ip),
            prefix_len = COALESCE(prefix_len, 24),
            address_purpose = COALESCE(address_purpose, application_type),
            remarks = COALESCE(remarks, description)
        WHERE deleted_at IS NULL
        """
    )


async def _ensure_sqlite_network_node_columns(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(network_node)")
    columns = {row[1] for row in result.fetchall()}
    if "port_layout" not in columns:
        await connection.exec_driver_sql("ALTER TABLE network_node ADD COLUMN port_layout JSON")
    if "on_canvas" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN on_canvas BOOLEAN NOT NULL DEFAULT 1"
        )
    if "device_model_id" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN device_model_id CHAR(36)"
        )
    if "contract_device_name" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN contract_device_name VARCHAR(100)"
        )
    if "design_model_id" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN design_model_id CHAR(36)"
        )
    if "network_role" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN network_role VARCHAR(20)"
        )
    if "device_group" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN device_group VARCHAR(80)"
        )
    if "device_groups" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_node ADD COLUMN device_groups JSON"
        )


async def _ensure_sqlite_uuid_hyphen_normalize(connection) -> None:
    """Normalize legacy hyphenated UUID strings to compact form for consistent lookups."""
    if not str(settings.database_url).startswith("sqlite"):
        return

    async def _normalize(table: str, column: str) -> None:
        result = await connection.exec_driver_sql(f"PRAGMA table_info({table})")
        cols = {row[1] for row in result.fetchall()}
        if column not in cols:
            return
        await connection.exec_driver_sql(
            f"""
            UPDATE {table}
            SET {column} = REPLACE({column}, '-', '')
            WHERE {column} IS NOT NULL AND INSTR({column}, '-') > 0
            """
        )

    # network project graph
    await _normalize("network_project", "id")
    await _normalize("network_project", "model_root_folder_id")
    await _normalize("network_topology", "id")
    await _normalize("network_topology", "project_id")
    await _normalize("network_node", "id")
    await _normalize("network_node", "topology_id")
    await _normalize("network_node", "design_model_id")
    await _normalize("network_link", "id")
    await _normalize("network_link", "topology_id")
    await _normalize("network_link", "source_node_id")
    await _normalize("network_link", "target_node_id")
    await _normalize("network_lab_session", "id")
    await _normalize("network_lab_session", "topology_id")
    await _normalize("network_model_folder", "id")
    await _normalize("network_model_folder", "parent_id")
    await _normalize("network_design_model", "id")
    await _normalize("network_design_model", "folder_id")
    await _normalize("network_wiring_rule", "id")
    await _normalize("network_wiring_rule", "topology_id")
    await _normalize("network_wiring_rule", "project_id")


async def _ensure_sqlite_network_project_model_folder(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(network_project)")
    columns = {row[1] for row in result.fetchall()}
    if "model_root_folder_id" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_project ADD COLUMN model_root_folder_id CHAR(36)"
        )


async def _ensure_sqlite_network_lab_session(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    tables = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='network_lab_session'"
    )
    if tables.fetchall():
        return
    await connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS network_lab_session (
          id CHAR(36) NOT NULL PRIMARY KEY,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          created_by CHAR(36),
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_by CHAR(36),
          deleted_at DATETIME,
          deleted_by CHAR(36),
          version INTEGER NOT NULL DEFAULT 1,
          topology_id CHAR(36) NOT NULL UNIQUE,
          engine VARCHAR(20) NOT NULL DEFAULT 'eve-ng',
          external_lab_path VARCHAR(500),
          status VARCHAR(30) NOT NULL DEFAULT 'idle',
          last_sync_at DATETIME,
          error_message TEXT,
          node_map JSON,
          node_status JSON
        )
        """
    )


async def _ensure_sqlite_device_model_panel_columns(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(device_model)")
    columns = {row[1] for row in result.fetchall()}
    if "port_layout" not in columns:
        await connection.exec_driver_sql("ALTER TABLE device_model ADD COLUMN port_layout JSON")
    if "apply_device_name" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE device_model ADD COLUMN apply_device_name VARCHAR(100)"
        )
    if "network_kind" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE device_model ADD COLUMN network_kind VARCHAR(20)"
        )


async def _ensure_sqlite_network_link_columns(connection) -> None:
    if not str(settings.database_url).startswith("sqlite"):
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(network_link)")
    columns = {row[1] for row in result.fetchall()}
    for name in (
        "source_label",
        "target_label",
        "cable_type",
        "interface_class",
        "link_role",
        "connection_type",
        "speed",
        "lag_group",
        "redundancy_path",
        "media",
        "module",
    ):
        if name not in columns:
            await connection.exec_driver_sql(
                f"ALTER TABLE network_link ADD COLUMN {name} VARCHAR(200)"
            )
    if "cable_length_m" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_link ADD COLUMN cable_length_m FLOAT"
        )
    if "wiring_rule_id" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_link ADD COLUMN wiring_rule_id CHAR(36)"
        )
    if "line_style" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_link ADD COLUMN line_style VARCHAR(40)"
        )


async def _ensure_sqlite_network_wiring_rule_project(connection) -> None:
    """Ensure network_wiring_rule.project_id exists; allow null topology_id for global rules."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    tables = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='network_wiring_rule'"
    )
    if not tables.fetchall():
        return
    result = await connection.exec_driver_sql("PRAGMA table_info(network_wiring_rule)")
    rows = result.fetchall()
    columns = {row[1]: row for row in rows}
    if "project_id" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE network_wiring_rule ADD COLUMN project_id CHAR(36)"
        )
    await connection.exec_driver_sql(
        """
        UPDATE network_wiring_rule
        SET project_id = (
          SELECT network_topology.project_id
          FROM network_topology
          WHERE network_topology.id = network_wiring_rule.topology_id
        )
        WHERE project_id IS NULL
          AND topology_id IS NOT NULL
        """
    )
    # topology_id 原先 NOT NULL；全局规则需允许为空 → 重建表
    topo_col = columns.get("topology_id")
    if topo_col is not None and int(topo_col[3] or 0) == 1:  # notnull flag
        await connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS network_wiring_rule__global (
              id CHAR(36) NOT NULL PRIMARY KEY,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              created_by CHAR(36),
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_by CHAR(36),
              deleted_at DATETIME,
              deleted_by CHAR(36),
              version INTEGER NOT NULL DEFAULT 1,
              project_id CHAR(36),
              topology_id CHAR(36),
              name VARCHAR(200) NOT NULL,
              enabled BOOLEAN NOT NULL DEFAULT 1,
              mode VARCHAR(20) NOT NULL DEFAULT 'sequential',
              config JSON,
              description TEXT
            )
            """
        )
        await connection.exec_driver_sql(
            """
            INSERT INTO network_wiring_rule__global (
              id, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, version,
              project_id, topology_id, name, enabled, mode, config, description
            )
            SELECT
              id, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by, version,
              project_id, topology_id, name, enabled, mode, config, description
            FROM network_wiring_rule
            """
        )
        await connection.exec_driver_sql("DROP TABLE network_wiring_rule")
        await connection.exec_driver_sql(
            "ALTER TABLE network_wiring_rule__global RENAME TO network_wiring_rule"
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_network_wiring_rule_project_id ON network_wiring_rule (project_id)"
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_network_wiring_rule_topology_id ON network_wiring_rule (topology_id)"
        )


async def _ensure_sqlite_network_project(connection) -> None:
    """Create network_project / topology.project_id for existing SQLite DBs without alembic."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    tables = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='network_project'"
    )
    if not tables.fetchall():
        await connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS network_project (
              id CHAR(36) NOT NULL PRIMARY KEY,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              created_by CHAR(36),
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_by CHAR(36),
              deleted_at DATETIME,
              deleted_by CHAR(36),
              version INTEGER NOT NULL DEFAULT 1,
              code VARCHAR(50) NOT NULL UNIQUE,
              name VARCHAR(100) NOT NULL,
              description TEXT
            )
            """
        )
    topo = await connection.exec_driver_sql("PRAGMA table_info(network_topology)")
    topo_cols = {row[1] for row in topo.fetchall()}
    if topo_cols and "project_id" not in topo_cols:
        await connection.exec_driver_sql(
            "ALTER TABLE network_topology ADD COLUMN project_id CHAR(36)"
        )
    # Backfill orphan topologies under DEFAULT project
    if not topo_cols:
        return
    orphans = await connection.exec_driver_sql(
        """
        SELECT COUNT(1) FROM network_topology
        WHERE deleted_at IS NULL AND project_id IS NULL
        """
    )
    orphan_count = orphans.fetchone()[0] if orphans else 0
    if orphan_count:
        existing = await connection.exec_driver_sql(
            "SELECT id FROM network_project WHERE code='DEFAULT' AND deleted_at IS NULL LIMIT 1"
        )
        row = existing.fetchone()
        if row:
            project_id = row[0]
        else:
            import uuid as _uuid

            project_id = str(_uuid.uuid4())
            await connection.exec_driver_sql(
                f"""
                INSERT INTO network_project (id, version, code, name, description)
                VALUES ('{project_id}', 1, 'DEFAULT', '默认项目', '自动创建，挂载已有拓扑')
                """
            )
        await connection.exec_driver_sql(
            f"""
            UPDATE network_topology
            SET project_id = '{project_id}'
            WHERE deleted_at IS NULL AND project_id IS NULL
            """
        )


async def _ensure_sqlite_warehouse_table(connection) -> None:
    """Create warehouse / warehouse_asset tables and soft-add columns for SQLite."""
    if not str(settings.database_url).startswith("sqlite"):
        return
    tables = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='warehouse'"
    )
    if not tables.fetchone():
        await connection.exec_driver_sql(
            """
            CREATE TABLE warehouse (
                room_id CHAR(32) NOT NULL,
                code VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                asset_ledger_ready BOOLEAN NOT NULL DEFAULT 1,
                id CHAR(32) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by CHAR(32),
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by CHAR(32),
                deleted_at DATETIME,
                deleted_by CHAR(32),
                version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (id),
                CONSTRAINT uk_warehouse_code UNIQUE (code),
                FOREIGN KEY(room_id) REFERENCES room (id)
            )
            """
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_warehouse_room_id ON warehouse (room_id)"
        )
    else:
        cols = await connection.exec_driver_sql("PRAGMA table_info(warehouse)")
        existing = {row[1] for row in cols.fetchall()}
        if "asset_ledger_ready" not in existing:
            await connection.exec_driver_sql(
                "ALTER TABLE warehouse ADD COLUMN asset_ledger_ready BOOLEAN NOT NULL DEFAULT 1"
            )

    asset_tables = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='warehouse_asset'"
    )
    if not asset_tables.fetchone():
        await connection.exec_driver_sql(
            """
            CREATE TABLE warehouse_asset (
                warehouse_id CHAR(32) NOT NULL,
                name VARCHAR(200) NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit VARCHAR(20) NOT NULL DEFAULT 'piece',
                project VARCHAR(200),
                application VARCHAR(200),
                category VARCHAR(30) NOT NULL DEFAULT 'other',
                status VARCHAR(30) NOT NULL DEFAULT 'new',
                inbound_at DATETIME,
                outbound_mode VARCHAR(20) NOT NULL DEFAULT 'undetermined',
                outbound_at DATETIME,
                owner_name VARCHAR(100),
                owner_contact VARCHAR(100),
                remark TEXT,
                id CHAR(32) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by CHAR(32),
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by CHAR(32),
                deleted_at DATETIME,
                deleted_by CHAR(32),
                version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (id),
                FOREIGN KEY(warehouse_id) REFERENCES warehouse (id)
            )
            """
        )
        await connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_warehouse_asset_warehouse_id ON warehouse_asset (warehouse_id)"
        )
        return

    asset_cols = await connection.exec_driver_sql("PRAGMA table_info(warehouse_asset)")
    asset_existing = {row[1] for row in asset_cols.fetchall()}
    if "quantity" not in asset_existing:
        await connection.exec_driver_sql(
            "ALTER TABLE warehouse_asset ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"
        )
    if "unit" not in asset_existing:
        await connection.exec_driver_sql(
            "ALTER TABLE warehouse_asset ADD COLUMN unit VARCHAR(20) NOT NULL DEFAULT 'piece'"
        )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_room_columns(conn)
        await _ensure_sqlite_rack_columns(conn)
        await _ensure_sqlite_rack_code_unique_per_room(conn)
        await _ensure_sqlite_device_columns(conn)
        await _ensure_sqlite_device_contract_columns(conn)
        await _ensure_sqlite_ip_address_columns(conn)
        await _ensure_sqlite_ip_segment(conn)
        await _ensure_sqlite_network_node_columns(conn)
        await _ensure_sqlite_network_link_columns(conn)
        await _ensure_sqlite_network_project(conn)
        await _ensure_sqlite_network_project_model_folder(conn)
        await _ensure_sqlite_network_lab_session(conn)
        await _ensure_sqlite_network_wiring_rule_project(conn)
        await _ensure_sqlite_uuid_hyphen_normalize(conn)
        await _ensure_sqlite_device_model_panel_columns(conn)
        await _ensure_sqlite_warehouse_table(conn)

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
