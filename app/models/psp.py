from sqlalchemy import Column, Integer, String, Float, Boolean
from app.database import Base


class PSP(Base):
    """
    Configuration for a simulated Payment Service Provider.

    In a real system this data (success rate, latency) would come from
    monitoring/health-check systems. Here we just store it directly so it
    can be tweaked from the dashboard for demo purposes.
    """

    __tablename__ = "psps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    success_rate = Column(Float, nullable=False)      # e.g. 0.92 for 92%
    avg_latency_ms = Column(Integer, nullable=False)   # simulated average latency
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<PSP {self.name} success={self.success_rate} active={self.is_active}>"
