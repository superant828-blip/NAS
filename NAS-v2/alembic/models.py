"""
Database models for NAS-v2
Alembic will use these models to generate migrations
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, BigInteger, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """User table"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='user')
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    files = relationship("File", back_populates="user", foreign_keys="File.user_id")
    albums = relationship("Album", back_populates="user")
    shares = relationship("Share", back_populates="user")
    trash = relationship("Trash", back_populates="user")


class File(Base):
    """File table"""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('files.id'), nullable=True)
    name = Column(String(255), nullable=False)
    path = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # 'file' or 'folder'
    size = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="files", foreign_keys=[user_id])
    parent = relationship("File", remote_side=[id], backref="children")


class Album(Base):
    """Album table"""
    __tablename__ = 'albums'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="albums")
    photos = relationship("Photo", back_populates="album")


class Photo(Base):
    """Photo table"""
    __tablename__ = 'photos'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    album_id = Column(Integer, ForeignKey('albums.id'), nullable=False)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    path = Column(Text, nullable=False)
    
    # Relationships
    album = relationship("Album", back_populates="photos")


class Share(Base):
    """Share table"""
    __tablename__ = 'shares'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    file_type = Column(String(50), nullable=False)  # 'file' or 'folder'
    file_id = Column(Integer, nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="shares")


class StoragePool(Base):
    """Storage pool table"""
    __tablename__ = 'storage_pools'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default='active')
    
    # Relationships
    datasets = relationship("Dataset", back_populates="pool")


class Dataset(Base):
    """Dataset table"""
    __tablename__ = 'datasets'
    
    id = Column(Integer, primary_key=True)
    pool_name = Column(String(255), ForeignKey('storage_pools.name'), nullable=False)
    name = Column(String(255), nullable=False)
    used = Column(BigInteger, default=0)
    available = Column(BigInteger, default=0)
    
    # Relationships
    pool = relationship("StoragePool", back_populates="datasets")
    snapshots = relationship("Snapshot", back_populates="dataset")


class Snapshot(Base):
    """Snapshot table"""
    __tablename__ = 'snapshots'
    
    id = Column(Integer, primary_key=True)
    dataset = Column(String(255), ForeignKey('datasets.name'), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    dataset_obj = relationship("Dataset", back_populates="snapshots")


class Trash(Base):
    """Trash table"""
    __tablename__ = 'trash'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    original_path = Column(Text, nullable=False)
    deleted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="trash")