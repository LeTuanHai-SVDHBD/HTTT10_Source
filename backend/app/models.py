from datetime import datetime
from sqlalchemy import String,Boolean,BigInteger,DateTime,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    employee_code:Mapped[str]=mapped_column(String(32))
    full_name:Mapped[str]=mapped_column(String(150))
    email:Mapped[str]=mapped_column(String(254))
    department_id:Mapped[str]=mapped_column(String(36))
    status:Mapped[str]=mapped_column(String(10))
    password_hash:Mapped[str|None]=mapped_column(String(255))
    must_change_password:Mapped[bool]=mapped_column(Boolean)
    auth_version:Mapped[int]=mapped_column(BigInteger)
    row_version:Mapped[int]=mapped_column(BigInteger)
class UserRole(Base):
    __tablename__='user_roles'
    user_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    role:Mapped[str]=mapped_column(String(16),primary_key=True)
    granted_by:Mapped[str]=mapped_column(String(36))
class AuthSession(Base):
    __tablename__='auth_sessions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    user_id:Mapped[str]=mapped_column(String(36))
    auth_version:Mapped[int]=mapped_column(BigInteger)
    issued_at:Mapped[datetime]=mapped_column(DateTime)
    expires_at:Mapped[datetime]=mapped_column(DateTime)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime)
