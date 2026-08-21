from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    buildings,
    dashboard,
    datacenters,
    device_contracts,
    devices,
    floors,
    health,
    ip_addresses,
    layout,
    network,
    network_lab,
    network_model_design,
    network_projects,
    personnel,
    rack_templates,
    racks,
    rooms,
    svg_audit,
    users,
    warehouses,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(datacenters.router, tags=["datacenters"])
api_router.include_router(buildings.router, tags=["buildings"])
api_router.include_router(floors.router, tags=["floors"])
api_router.include_router(rooms.router, tags=["rooms"])
api_router.include_router(warehouses.router, tags=["warehouses"])
api_router.include_router(racks.router, tags=["racks"])
api_router.include_router(rack_templates.router, tags=["rack-templates"])
api_router.include_router(devices.router, tags=["devices"])
api_router.include_router(device_contracts.router, tags=["device-contracts"])
api_router.include_router(personnel.router)
api_router.include_router(network_lab.router, tags=["network-lab"])
api_router.include_router(network.router, tags=["network"])
api_router.include_router(network_projects.router, tags=["network"])
api_router.include_router(network_model_design.router, tags=["network"])
api_router.include_router(ip_addresses.router)
api_router.include_router(layout.router, tags=["layout"])
api_router.include_router(svg_audit.router, tags=["svg", "audit"])
api_router.include_router(users.router, tags=["users", "roles"])
