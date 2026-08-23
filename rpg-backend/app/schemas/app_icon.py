from pydantic import BaseModel


class AppIconOut(BaseModel):
    key: str
    image_path: str | None


class AppIconAdminOut(BaseModel):
    id: int
    key: str
    label: str
    image_path: str | None
