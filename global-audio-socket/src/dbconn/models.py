from sqlalchemy import Boolean, Column, Integer, String, DateTime, JSON
from .database import Base
from datetime import datetime, timezone

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    caller_id = Column(String, index=True)
    event_type = Column(String, index=True)
    event_detail = Column(String, nullable=True)
    inserted_on_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class DockerCallHandler(Base):
    __tablename__="docker_callhandler"

    id = Column(Integer, primary_key=True, index=True)
    container_name = Column(String, index=True)
    container_ip = Column(String, index=True)
    extension = Column(Integer, index=True)
    client_id = Column(Integer, index=True)
    max_clients = Column(Integer, index=True)
    active = Column(Boolean, index=True)
    data_json = Column(JSON)
    modified_on_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class UserDetails(Base):
    __tablename__="user_details"

    id = Column(Integer, primary_key=True, index=True)
    caller_id = Column(String, index=True)
    name = Column(String, index=True)
    phone_number = Column(String, index=True)
    call_type = Column(JSON)
    tts_folder_location = Column(String, index=True)
    status = Column(String, index=True)
    assigned_container = Column(String, index=True)
    scheduled_for_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    modified_on_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# class VoIPUsers(Base):
#     __tablename__ = "voip_users"

#     id = Column(Integer, primary_key=True, index=True)
#     server_ip = Column(String, index=True)
#     host_ip = Column(String, index=True)
#     status = Column(String, index=True)
#     modified_on_utc = Column(DateTime, default=lambda: datetime.now(timezone.utc))
