from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.utils.encryption import get_encryptor
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    emails = relationship("EmailMetadata", back_populates="user", cascade="all, delete-orphan")

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    email = Column(String, nullable=False)     # Authorized inbox email address
    _access_token = Column("access_token", Text, nullable=False)
    _refresh_token = Column("refresh_token", Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tokens")

    @property
    def access_token(self) -> str:
        return get_encryptor().decrypt(self._access_token)

    @access_token.setter
    def access_token(self, val: str):
        self._access_token = get_encryptor().encrypt(val)

    @property
    def refresh_token(self) -> str:
        return get_encryptor().decrypt(self._refresh_token) if self._refresh_token else ""

    @refresh_token.setter
    def refresh_token(self, val: str):
        if val:
            self._refresh_token = get_encryptor().encrypt(val)
        else:
            self._refresh_token = None

