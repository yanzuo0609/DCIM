from pydantic import BaseModel, Field


class RackMountBody(BaseModel):
    device_id: str
    u_position: int = Field(ge=1, description="Starting U position (bottom-up, U1 at bottom)")


class MountRequest(BaseModel):
    device_id: str
    rack_id: str
    u_position: int = Field(ge=1, description="Starting U position (bottom-up, U1 at bottom)")


class UnmountRequest(BaseModel):
    device_id: str


class ValidateLayoutRequest(BaseModel):
    rack_id: str
    u_position: int = Field(ge=1)
    height_u: int = Field(ge=1, le=10)
    exclude_device_id: str | None = None


class ValidateLayoutResponse(BaseModel):
    valid: bool
    message: str
    occupied_positions: list[int] = Field(default_factory=list)


class AutoLayoutRequest(BaseModel):
    rack_id: str
    device_id: str


class AutoLayoutResponse(BaseModel):
    u_position: int | None
    message: str
