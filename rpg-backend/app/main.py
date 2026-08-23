from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.db_guard import assert_not_football_database
from app.core.exceptions import register_exception_handlers
from app.routers import (
    admin_app_icons,
    admin_chests,
    admin_classes,
    admin_enemies,
    admin_expeditions,
    admin_hero_templates,
    admin_items,
    admin_quests,
    admin_races,
    admin_users,
    app_icons,
    arena,
    auth,
    battles,
    campaign,
    catalog,
    chests,
    economy,
    enemies,
    expeditions,
    heroes,
    inventory,
    items,
    leaderboards,
    minigames,
    profile,
    quests,
    skills,
)

settings = get_settings()

assert_not_football_database(settings.database_url)

if settings.environment == "production" and settings.dev_mode:
    raise RuntimeError("dev_mode must be disabled when environment=production")

app = FastAPI(
    title="Medieval RPG API",
    docs_url=None if settings.environment == "production" else "/api/docs",
    redoc_url=None if settings.environment == "production" else "/api/redoc",
    openapi_url=None if settings.environment == "production" else "/api/openapi.json",
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
app.include_router(catalog.router, prefix=API_PREFIX, tags=["catalog"])
app.include_router(heroes.router, prefix=f"{API_PREFIX}/heroes", tags=["heroes"])
app.include_router(skills.router, prefix=f"{API_PREFIX}/heroes/me/skills", tags=["skills"])
app.include_router(items.router, prefix=f"{API_PREFIX}/item-templates", tags=["items"])
app.include_router(inventory.router, prefix=f"{API_PREFIX}/heroes/me", tags=["inventory"])
app.include_router(economy.router, prefix=f"{API_PREFIX}/economy", tags=["economy"])
app.include_router(chests.router, prefix=f"{API_PREFIX}/chests", tags=["chests"])
app.include_router(admin_chests.router, prefix=f"{API_PREFIX}/admin/chests", tags=["admin"])
app.include_router(admin_races.router, prefix=f"{API_PREFIX}/admin/races", tags=["admin"])
app.include_router(admin_classes.router, prefix=f"{API_PREFIX}/admin/classes", tags=["admin"])
app.include_router(admin_hero_templates.router, prefix=f"{API_PREFIX}/admin/hero-templates", tags=["admin"])
app.include_router(admin_enemies.router, prefix=f"{API_PREFIX}/admin/enemies", tags=["admin"])
app.include_router(admin_items.router, prefix=f"{API_PREFIX}/admin/items", tags=["admin"])
app.include_router(admin_expeditions.router, prefix=f"{API_PREFIX}/admin/expeditions", tags=["admin"])
app.include_router(admin_quests.router, prefix=f"{API_PREFIX}/admin/quests", tags=["admin"])
app.include_router(admin_users.router, prefix=f"{API_PREFIX}/admin/users", tags=["admin"])
app.include_router(enemies.router, prefix=f"{API_PREFIX}/enemies", tags=["battles"])
app.include_router(battles.router, prefix=f"{API_PREFIX}/battles", tags=["battles"])
app.include_router(expeditions.router, prefix=f"{API_PREFIX}/expeditions", tags=["expeditions"])
app.include_router(expeditions.hero_router, prefix=f"{API_PREFIX}/heroes/me", tags=["expeditions"])
app.include_router(quests.router, prefix=f"{API_PREFIX}/quests", tags=["quests"])
app.include_router(arena.router, prefix=f"{API_PREFIX}/arena/matches", tags=["arena"])
app.include_router(campaign.router, prefix=f"{API_PREFIX}/campaign", tags=["campaign"])
app.include_router(profile.router, prefix=f"{API_PREFIX}/profile", tags=["profile"])
app.include_router(leaderboards.router, prefix=f"{API_PREFIX}/leaderboards", tags=["leaderboards"])
app.include_router(minigames.router, prefix=f"{API_PREFIX}/minigames", tags=["minigames"])
app.include_router(app_icons.router, prefix=f"{API_PREFIX}/app-icons", tags=["app-icons"])
app.include_router(admin_app_icons.router, prefix=f"{API_PREFIX}/admin/app-icons", tags=["admin"])

# Admin-uploaded template images (services/image_service.py) — no
# AI-generation pipeline, no versioning, just a plain file behind the
# image_path column every catalog model already had. Directory is created
# lazily by image_service on first upload, not here.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
