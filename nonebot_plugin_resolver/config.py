from pydantic import BaseModel
from pydantic import Field


class Config(BaseModel):
    xhs_ck: str = Field(default="")
    douyin_ck: str = Field(default="")
    is_oversea: bool = Field(default=False)
    is_lagrange: bool = Field(default=False)
    bili_sessdata: str = Field(default="")
    r_global_nickname: str = Field(default="")
    resolver_proxy: str = Field(default="http://127.0.0.1:7890")
    video_duration_maximum: int = Field(default=480)
    download_video: bool = Field(default=True)
