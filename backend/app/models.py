from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Participant(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore", allow_inf_nan=False)
    id: str
    name: str = Field(min_length=2, max_length=80)
    type: Literal["consumer", "prosumer"]
    load_kw: float = Field(ge=0, le=1000)
    solar_kwp: float = Field(default=0, ge=0, le=1000)
    community_id: str | None = None

    @model_validator(mode="after")
    def check_solar(self):
        if self.type == "consumer" and self.solar_kwp != 0:
            raise ValueError("Consumers must have zero solar capacity.")
        if self.type == "prosumer" and self.solar_kwp <= 0:
            raise ValueError("Enter a solar capacity greater than zero for a prosumer.")
        return self


class MarketSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    grid_buy: float = Field(default=0.30, ge=0, le=10)
    grid_sell: float = Field(default=0.08, ge=0, le=10)
    price_weight: float = Field(default=0.60, ge=0, le=1)
    transport_fee: float = Field(default=0.015, ge=0, le=10)
    buyer_transport_share: float = Field(default=0.50, ge=0, le=1)
    solar_yield_factor: float = Field(default=0.75, ge=0, le=1)

    @model_validator(mode="after")
    def check_tariffs(self):
        if self.grid_sell > self.grid_buy:
            raise ValueError("Grid export price cannot exceed the grid import price.")
        return self
