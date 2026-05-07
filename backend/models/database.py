"""
Database models - SQLAlchemy ORM
SQLite for development, easily swap to PostgreSQL in production
"""
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "tenderai.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Tender(Base):
    __tablename__ = "tenders"
    id           = Column(String, primary_key=True)
    ref          = Column(String, unique=True, nullable=False)
    name         = Column(String, nullable=False)
    org          = Column(String, nullable=False)
    value        = Column(Float, default=0)
    min_turnover = Column(Float, default=5)
    min_projects = Column(Integer, default=3)
    emd          = Column(Float, default=0)
    description  = Column(Text, default="")
    proc_type    = Column(String, default="Open Tender Enquiry (OTE)")
    deadline     = Column(String, default="")
    criteria_json= Column(Text, default="[]")
    file_path    = Column(String, default="")
    created_at   = Column(DateTime, default=datetime.utcnow)
    bidders      = relationship("Bidder", back_populates="tender", cascade="all, delete-orphan")
    evaluations  = relationship("Evaluation", back_populates="tender", cascade="all, delete-orphan")
    audit_logs   = relationship("AuditLog", back_populates="tender", cascade="all, delete-orphan")


class Bidder(Base):
    __tablename__ = "bidders"
    id           = Column(String, primary_key=True)
    tender_id    = Column(String, ForeignKey("tenders.id"), nullable=False)
    company      = Column(String, nullable=False)
    gstin        = Column(String, default="")
    pan          = Column(String, default="")
    cin          = Column(String, default="")
    state        = Column(String, default="")
    net_worth    = Column(Float, nullable=True)
    turnover_21_22 = Column(Float, nullable=True)
    turnover_22_23 = Column(Float, nullable=True)
    turnover_23_24 = Column(Float, nullable=True)
    avg_turnover = Column(Float, default=0)
    projects     = Column(Integer, default=0)
    exp_text     = Column(Text, default="")
    docs_list    = Column(Text, default="")   # comma-separated doc names
    gstn_valid   = Column(Boolean, default=False)
    file_paths   = Column(Text, default="")   # JSON list of uploaded file paths
    created_at   = Column(DateTime, default=datetime.utcnow)
    tender       = relationship("Tender", back_populates="bidders")
    evaluations  = relationship("Evaluation", back_populates="bidder", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"
    id              = Column(String, primary_key=True)
    tender_id       = Column(String, ForeignKey("tenders.id"), nullable=False)
    bidder_id       = Column(String, ForeignKey("bidders.id"), nullable=False)
    overall_status  = Column(String, default="pending")
    confidence      = Column(Float, default=0)
    mandatory_pass  = Column(Integer, default=0)
    mandatory_total = Column(Integer, default=0)
    optional_score  = Column(Float, default=0)
    has_review      = Column(Boolean, default=False)
    results_json    = Column(Text, default="[]")
    report_json     = Column(Text, default="{}")
    evaluated_at    = Column(DateTime, default=datetime.utcnow)
    tender          = relationship("Tender", back_populates="evaluations")
    bidder          = relationship("Bidder", back_populates="evaluations")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id           = Column(String, primary_key=True)
    tender_id    = Column(String, ForeignKey("tenders.id"), nullable=True)
    bidder_id    = Column(String, nullable=True)
    event_type   = Column(String, nullable=False)
    description  = Column(Text, nullable=False)
    actor        = Column(String, default="system")
    status       = Column(String, default="info")   # ok / err / info
    prev_hash    = Column(String, default="GENESIS")
    event_hash   = Column(String, default="")
    created_at   = Column(DateTime, default=datetime.utcnow)
    tender       = relationship("Tender", back_populates="audit_logs")


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialised")


if __name__ == "__main__":
    init_db()
