from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_PAYMENT_METHODS = {"UPI", "CARD", "NETBANKING", "WALLET"}
SUPPORTED_CURRENCIES = {"INR", "USD"}


class PaymentCreateRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    payment_method: str
    customer_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v):
        if v.upper() not in SUPPORTED_PAYMENT_METHODS:
            raise ValueError(
                f"payment_method must be one of {sorted(SUPPORTED_PAYMENT_METHODS)}"
            )
        return v.upper()

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        if v.upper() not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {sorted(SUPPORTED_CURRENCIES)}")
        return v.upper()


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    order_id: str
    customer_id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    selected_psp: Optional[str] = None
    attempted_psps: Optional[str] = None
    retry_count: int
    processing_time_ms: int
    created_at: datetime
    updated_at: datetime
