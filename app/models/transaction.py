import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


def generate_transaction_id():
    # short, readable transaction id - not trying to be a real UUID everywhere
    return "TXN" + uuid.uuid4().hex[:10].upper()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, unique=True, index=True, default=generate_transaction_id)

    order_id = Column(String, index=True, nullable=False)
    customer_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    payment_method = Column(String, nullable=False)

    # this is the field that prevents duplicate payments - see routing_service /
    # payment_service for how it's used
    idempotency_key = Column(String, unique=True, index=True, nullable=False)

    status = Column(String, default="CREATED")  # CREATED, PROCESSING, SUCCESS, FAILED, RETRYING

    selected_psp = Column(String, nullable=True)       # PSP that ultimately handled the payment
    attempted_psps = Column(String, default="")         # comma separated list, kept simple on purpose
    retry_count = Column(Integer, default=0)
    processing_time_ms = Column(Integer, default=0)     # total simulated time across all attempts

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Transaction {self.transaction_id} status={self.status}>"
