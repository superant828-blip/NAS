"""API插件系统"""
from fastapi import APIRouter

def get_routers():
    from . import auth, files, albums, shares, storage, users, system, jobs, events, config
    return [
        auth.router,
        files.router,
        albums.router,
        shares.router,
        shares.share_router,
        shares.smb_router,
        shares.nfs_router,
        shares.links_router,
        config.router,
        storage.router,
        storage.snapshot_router,
        users.router,
        system.router,
        auth.password_router,
        jobs.router,
        events.router,
    ]