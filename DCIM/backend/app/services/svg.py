import re
import uuid
from xml.sax.saxutils import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.device import DeviceRepository
from app.repositories.rack import RackRepository

_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)


def _ip_summary(device) -> str:
    rows = list(getattr(device, "ip_addresses", None) or [])
    if rows:
        for row in rows:
            if getattr(row, "system_ip", None):
                return row.system_ip
        if rows[0].system_ip:
            return rows[0].system_ip
    hostname = (device.hostname or "").strip()
    if hostname and _IPV4_RE.fullmatch(hostname):
        return hostname
    description = device.description
    if description:
        match = _IPV4_RE.search(description)
        if match:
            return match.group(0)
    return "—"


def _height_colors(height_u: int) -> tuple[str, str]:
    if height_u == 2:
        return "#1f6f6a", "#2bb5a8"
    if height_u == 4:
        return "#8a5a1e", "#e0a04a"
    return "#2f4d7a", "#6a9adf"


class SVGService:
    """Export-oriented rack diagram (download/print). Interactive view uses RackCabinet UI."""

    U_HEIGHT = 22
    RACK_WIDTH = 360
    PADDING = 16
    LABEL_W = 40
    COL_DEVICE = 150
    COL_IP = 90
    COL_POWER = 70

    def __init__(self, session: AsyncSession) -> None:
        self.rack_repo = RackRepository(session)
        self.device_repo = DeviceRepository(session)

    async def render_rack(self, rack_id: uuid.UUID) -> str:
        rack = await self.rack_repo.get_by_id_with_positions(rack_id)
        if not rack:
            raise NotFoundError("Rack not found")

        devices = await self.device_repo.list_by_rack(rack_id)
        device_by_u: dict[int, object] = {}
        total_power = 0.0
        for device in devices:
            if device.u_position is None:
                continue
            if device.power is not None:
                total_power += float(device.power)
            for offset in range(device.height_u):
                device_by_u[device.u_position + offset] = device

        header_h = 48
        footer_h = 28
        frame_h = rack.total_u * self.U_HEIGHT
        width = self.PADDING * 2 + self.RACK_WIDTH
        height = self.PADDING * 2 + header_h + frame_h + footer_h

        power_label = (
            f"{total_power / 1000:.1f} kW" if total_power >= 1000 else f"{int(round(total_power))} W"
        )

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" fill="#12161e"/>',
            f'<rect x="{self.PADDING}" y="{self.PADDING}" width="{self.RACK_WIDTH}" '
            f'height="{header_h + frame_h + footer_h}" fill="#1a1f2a" stroke="#3d4658" stroke-width="1.5" rx="4"/>',
            # Header: power | code | U
            f'<text x="{self.PADDING + 12}" y="{self.PADDING + 18}" font-size="10" fill="#8b95a8">'
            f'功率</text>',
            f'<text x="{self.PADDING + 12}" y="{self.PADDING + 34}" font-size="13" font-weight="700" fill="#7ddea8">'
            f'{escape(power_label)}</text>',
            f'<text x="{width / 2}" y="{self.PADDING + 30}" text-anchor="middle" '
            f'font-family="Consolas, monospace" font-size="15" font-weight="700" fill="#f0d78c">'
            f'{escape(rack.code)}</text>',
            f'<text x="{width - self.PADDING - 12}" y="{self.PADDING + 30}" text-anchor="end" '
            f'font-size="12" fill="#8b95a8">{rack.total_u}U</text>',
        ]

        # Column headers
        col_y = self.PADDING + header_h - 6
        frame_x = self.PADDING
        frame_y = self.PADDING + header_h
        x_u = frame_x + 8
        x_dev = frame_x + self.LABEL_W
        x_ip = x_dev + self.COL_DEVICE
        x_pwr = x_ip + self.COL_IP

        lines.append(
            f'<text x="{x_u}" y="{col_y}" font-size="9" fill="#8b95a8">U</text>'
            f'<text x="{x_dev}" y="{col_y}" font-size="9" fill="#8b95a8">设备</text>'
            f'<text x="{x_ip}" y="{col_y}" font-size="9" fill="#8b95a8">IP</text>'
            f'<text x="{x_pwr}" y="{col_y}" font-size="9" fill="#8b95a8">功率</text>'
        )

        rendered: set[uuid.UUID] = set()
        for u in range(rack.total_u, 0, -1):
            y = frame_y + (rack.total_u - u) * self.U_HEIGHT
            device = device_by_u.get(u)
            if device is None:
                lines.append(
                    f'<rect x="{frame_x + 4}" y="{y + 1}" width="{self.RACK_WIDTH - 8}" '
                    f'height="{self.U_HEIGHT - 2}" fill="rgba(255,255,255,0.04)" rx="2"/>'
                )
                lines.append(
                    f'<text x="{x_u}" y="{y + 15}" font-size="10" fill="#c5cddc">U{u}</text>'
                    f'<text x="{x_dev}" y="{y + 15}" font-size="11" fill="#8b95a8">空闲</text>'
                    f'<text x="{x_ip}" y="{y + 15}" font-size="10" fill="#8b95a8">—</text>'
                    f'<text x="{x_pwr + self.COL_POWER - 8}" y="{y + 15}" text-anchor="end" '
                    f'font-size="10" fill="#8b95a8">—</text>'
                )
                continue

            is_top = device.u_position + device.height_u - 1 == u
            fill, stroke = _height_colors(device.height_u)
            if is_top and device.id not in rendered:
                rendered.add(device.id)
                block_h = device.height_u * self.U_HEIGHT - 2
                lines.append(
                    f'<rect x="{frame_x + 4}" y="{y + 1}" width="{self.RACK_WIDTH - 8}" '
                    f'height="{block_h}" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="3"/>'
                )
                power = float(device.power) if device.power is not None else None
                power_txt = "—" if power is None else (
                    f"{power / 1000:.1f}kW" if power >= 1000 else f"{int(round(power))}W"
                )
                ip = _ip_summary(device)
                badge = f"{device.height_u}U"
                lines.append(
                    f'<text x="{x_u}" y="{y + 15}" font-size="10" fill="#e8edf5">U{u}</text>'
                    f'<text x="{x_dev}" y="{y + 15}" font-size="10" font-weight="700" fill="#fff">'
                    f'[{escape(badge)}] {escape(device.hostname)}</text>'
                    f'<text x="{x_ip}" y="{y + 15}" font-size="10" fill="#e8edf5">{escape(ip)}</text>'
                    f'<text x="{x_pwr + self.COL_POWER - 8}" y="{y + 15}" text-anchor="end" '
                    f'font-size="10" font-weight="600" fill="#e8edf5">{escape(power_txt)}</text>'
                )
            else:
                lines.append(
                    f'<text x="{x_u}" y="{y + 15}" font-size="10" fill="#e8edf5">U{u}</text>'
                )

        # Footer legend
        fy = frame_y + frame_h + 18
        lines.append(
            f'<text x="{self.PADDING + 12}" y="{fy}" font-size="10" fill="#2bb5a8">■ 2U</text>'
            f'<text x="{self.PADDING + 60}" y="{fy}" font-size="10" fill="#e0a04a">■ 4U</text>'
            f'<text x="{self.PADDING + 110}" y="{fy}" font-size="10" fill="#6a9adf">■ 其它</text>'
            f'<text x="{self.PADDING + 170}" y="{fy}" font-size="10" fill="#8b95a8">■ 空闲</text>'
            f'<text x="{width - self.PADDING - 12}" y="{fy}" text-anchor="end" font-size="10" fill="#8b95a8">'
            f'{escape(rack.name)}</text>'
        )
        lines.append("</svg>")
        return "\n".join(lines)
