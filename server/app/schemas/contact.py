from pydantic import BaseModel


class ContactResponse(BaseModel):
    id: int
    wechat_nickname: str | None
    wechat_id: str | None
    tag: str | None
    status: str | None
    remark: str | None
