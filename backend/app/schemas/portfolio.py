from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    ticker: str
    name: str | None = None
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)


class HoldingResponse(BaseModel):
    id: int
    ticker: str
    name: str | None
    quantity: float
    avg_price: float

    model_config = {"from_attributes": True}
