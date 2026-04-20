"""SQLAlchemy modelleri ve session yönetimi.

Hem PostgreSQL (production) hem SQLite (local dev) destekler.
DATABASE_URL environment variable'ı ile belirlenir:
  - postgresql://user:pass@host:5432/db
  - sqlite:///adsyield.db
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON, Numeric
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///adsyield.db")

# SQLite için check_same_thread=False, PostgreSQL için yok
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Modeller ---

class Publisher(Base):
    __tablename__ = "publishers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    management_key = Column(Text, nullable=False)
    gam_publisher_id = Column(Text, nullable=False)
    notify_email = Column(Text, default="")
    mode = Column(Text, default="manual")  # manual | hybrid
    frequency_days = Column(Integer, default=2)
    active = Column(Integer, default=1)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    apps = relationship("App", back_populates="publisher", cascade="all, delete-orphan")


class App(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publisher_id = Column(Integer, ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False)
    label = Column(Text, nullable=False)         # "Mackolik AOS"
    gam_app_name = Column(Text, nullable=False)  # "Mackolik" — GAM path'deki klasör adı
    platform = Column(Text, nullable=False)      # aos | ios
    active = Column(Integer, default=1)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    publisher = relationship("Publisher", back_populates="apps")
    slots = relationship("SlotCache", back_populates="app", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="app", cascade="all, delete-orphan")


class SlotCache(Base):
    """GAM'den çekilen slot durumunun cache'i. Günlük 03:00 sync edilir."""
    __tablename__ = "slot_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    format = Column(Text, nullable=False)    # bnr, int, mrec, mrec2, rew
    platform = Column(Text, nullable=False)  # aos, ios
    cpm = Column(Numeric(10, 2), nullable=False)
    max_version = Column(Integer, nullable=False)
    synced_at = Column(DateTime, default=datetime.utcnow)

    app = relationship("App", back_populates="slots")


class Snapshot(Base):
    """Her run öncesi alınan snapshot — rollback için."""
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    run_job_id = Column(Text, nullable=False)
    max_ad_unit_id = Column(Text, nullable=False)
    max_ad_unit_name = Column(Text, default="")
    network_ad_unit_id_old = Column(Text, nullable=False)
    network_ad_unit_id_new = Column(Text, nullable=False)
    full_config = Column(JSON, nullable=True)  # Run öncesi ad_network_settings (rollback için)
    status = Column(Text, default="active")    # active | rolled_back
    created_at = Column(DateTime, default=datetime.utcnow)
    rolled_back_at = Column(DateTime, nullable=True)

    app = relationship("App", back_populates="snapshots")


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publisher_id = Column(Integer, ForeignKey("publishers.id", ondelete="SET NULL"), nullable=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="SET NULL"), nullable=True)
    publisher_name = Column(Text)
    app_label = Column(Text)
    run_job_id = Column(Text)
    ad_unit_id = Column(Text)
    ad_unit_name = Column(Text)
    old_value = Column(Text)
    new_value = Column(Text)
    status = Column(Text)  # SUCCESS | FAILED | DRY_RUN | ROLLED_BACK
    error_message = Column(Text, default="")
    ran_at = Column(DateTime, default=datetime.utcnow)


class PendingApproval(Base):
    """Hibrit mod dry run sonuçları, AM onayı bekliyor."""
    __tablename__ = "pending_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Text, unique=True, nullable=False)
    matched = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    status = Column(Text, default="pending")  # pending | approved | expired
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)


# --- Session yardımcıları ---

def get_session():
    """Context manager olarak kullanmak için."""
    return SessionLocal()

def init_db():
    """Tüm tabloları oluştur (IF NOT EXISTS)."""
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Veritabani hazir — {DATABASE_URL.split('://')[0]}")


if __name__ == "__main__":
    init_db()
