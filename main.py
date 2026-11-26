from datetime import datetime
import os
from pathlib import Path
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "td_connex.db")))
SCHEMA_PATH = BASE_DIR / "schema.sql"
FRONTEND_INDEX = BASE_DIR.parent / "frontend" / "index.html"

app = FastAPI(title="TDConnex Automation Downtime API", version="2.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", include_in_schema=False)
def serve_frontend():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return {"status": "TDConnex API running", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "tdconnex"}


class DowntimeCreate(BaseModel):
    date: str
    unit: str = Field(..., pattern="^(Unit 1|Unit 2)$")
    equipment: str
    shift: str
    category: str
    severity: str = Field(..., pattern="^(Red|Amber|Yellow)$")
    duration_min: int = Field(..., gt=0)
    spare_sku: Optional[str] = None
    spare_qty: int = Field(0, ge=0)
    problem_desc: Optional[str] = None
    root_cause: str
    image_data: Optional[str] = None
    action_taken: str
    technician: str
    auto_capa: bool = True


class SpareCreate(BaseModel):
    sku: str
    unit: str = Field(..., pattern="^(Unit 1|Unit 2)$")
    model: str
    category: str = "Automation"
    stock: int = Field(..., ge=0)
    min_stock: int = Field(2, ge=1)
    unit_cost: float = Field(..., ge=0)


class PmVerify(BaseModel):
    verified_by: str


class KaizenCreate(BaseModel):
    title: str
    area: str
    category: str
    owner: str
    problem: str
    countermeasure: str
    before_image: Optional[str] = None
    after_image: Optional[str] = None
    saving: str


def compute_spare_status(stock: int, min_stock: int) -> str:
    if stock <= 0:
        return "Out of Stock"
    if stock < min_stock:
        return "Low Stock"
    return "In Stock"


@app.post("/api/downtimes")
def create_downtime(payload: DowntimeCreate):
    now_id = datetime.utcnow().strftime("%H%M%S%f")[:10]
    dt_id = f"DT-{now_id}"
    spare_model = "None"
    spare_cost = 0.0
    updated_spare = None

    with get_conn() as conn:
        if payload.spare_sku and payload.spare_qty > 0:
            row = conn.execute(
                "SELECT * FROM spare_parts WHERE sku = ? AND unit = ?",
                (payload.spare_sku, payload.unit),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Spare part not available in spare list")
            if row["stock"] < payload.spare_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock in {payload.unit}: {row['stock']} available, {payload.spare_qty} requested",
                )
            new_stock = row["stock"] - payload.spare_qty
            spare_model = row["model"]
            spare_cost = row["unit_cost"] * payload.spare_qty
            conn.execute(
                "UPDATE spare_parts SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE sku = ? AND unit = ?",
                (new_stock, payload.spare_sku, payload.unit),
            )
            status_label = compute_spare_status(new_stock, row["min_stock"])
            updated_spare = {"sku": payload.spare_sku, "unit": payload.unit, "remaining": new_stock, "status": status_label}

            if new_stock < row["min_stock"]:
                notif_type = "critical" if new_stock == 0 else "warning"
                conn.execute(
                    "INSERT INTO notifications (id, type, title, message) VALUES (?, ?, ?, ?)",
                    (
                        f"N-SP-{now_id}",
                        notif_type,
                        f"{status_label}: {payload.spare_sku} ({payload.unit})",
                        f"{spare_model} dropped to {new_stock} units after {payload.spare_qty}x consumed in {dt_id}.",
                    ),
                )

        conn.execute(
            """
            INSERT INTO downtime_records
            (id, date, unit, equipment, shift, category, severity, duration_min, spare_sku, spare_model, spare_qty, spare_cost, root_cause, action_taken, technician, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
            """,
            (
                dt_id, payload.date, payload.unit, payload.equipment, payload.shift,
                payload.category, payload.severity, payload.duration_min,
                payload.spare_sku, spare_model, payload.spare_qty, spare_cost,
                payload.root_cause, payload.action_taken, payload.technician,
            ),
        )

        if payload.severity == "Red":
            conn.execute(
                "INSERT INTO notifications (id, type, title, message) VALUES (?, 'critical', ?, ?)",
                (f"N-RD-{now_id}", f"Red Status Alert: {payload.equipment} ({payload.unit})", payload.root_cause),
            )
            if payload.auto_capa:
                conn.execute(
                    "INSERT INTO actions (id, title, unit, priority, owner, due_date, status) VALUES (?, ?, ?, 'High', ?, ?, 'Pending')",
                    (f"ACT-{now_id[:6]}", f"CAPA for {dt_id}: {payload.root_cause[:60]}", payload.unit, payload.technician, payload.date),
                )

    return {"id": dt_id, "spare_cost": spare_cost, "updated_spare": updated_spare}


@app.get("/api/downtimes")
def list_downtimes(unit: Optional[str] = Query(None)):
    with get_conn() as conn:
        if unit in ("Unit 1", "Unit 2"):
            rows = conn.execute("SELECT * FROM downtime_records WHERE unit = ? ORDER BY created_at DESC", (unit,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM downtime_records ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@app.get("/api/spares")
def list_spares(unit: Optional[str] = Query(None)):
    with get_conn() as conn:
        if unit in ("Unit 1", "Unit 2"):
            rows = conn.execute("SELECT * FROM spare_parts WHERE unit = ? ORDER BY sku", (unit,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM spare_parts ORDER BY unit, sku").fetchall()
        return [{**dict(r), "status": compute_spare_status(r["stock"], r["min_stock"])} for r in rows]


@app.post("/api/spares")
def add_spare(payload: SpareCreate):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO spare_parts (sku, unit, model, category, stock, min_stock, unit_cost) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.sku, payload.unit, payload.model, payload.category, payload.stock, payload.min_stock, payload.unit_cost),
        )
    return {"status": "created", "sku": payload.sku, "unit": payload.unit}


@app.post("/api/spares/{unit}/{sku}/restock")
def restock_spare(unit: str, sku: str, qty: int = Query(5, gt=0)):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE spare_parts SET stock = stock + ?, updated_at = CURRENT_TIMESTAMP WHERE sku = ? AND unit = ?",
            (qty, sku, unit),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Spare not found")
        row = conn.execute("SELECT * FROM spare_parts WHERE sku = ? AND unit = ?", (sku, unit)).fetchone()
        return {**dict(row), "status": compute_spare_status(row["stock"], row["min_stock"])}


@app.post("/api/pm/{pm_id}/verify")
def verify_pm(pm_id: str, payload: PmVerify):
    with get_conn() as conn:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cur = conn.execute(
            "UPDATE pm_schedules SET status = 'Completed', verified_by = ?, verified_at = ? WHERE id = ?",
            (payload.verified_by, today, pm_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="PM task not found")
        return {"id": pm_id, "status": "Completed", "verified_by": payload.verified_by, "verified_at": today}


@app.post("/api/kaizen")
def create_kaizen(payload: KaizenCreate):
    kz_id = "KZ-" + datetime.utcnow().strftime("%H%M%S")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kaizens (id, title, area, category, owner, submitted_date, problem, countermeasure, saving, stage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted')",
            (kz_id, payload.title, payload.area, payload.category, payload.owner, today, payload.problem, payload.countermeasure, payload.saving),
        )
    return {"id": kz_id, "status": "Submitted"}


@app.get("/api/kaizen")
def list_kaizens():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM kaizens ORDER BY submitted_date DESC").fetchall()]


@app.get("/api/analytics/summary")
def analytics_summary(unit: Optional[str] = Query(None)):
    with get_conn() as conn:
        where = "WHERE unit = ?" if unit in ("Unit 1", "Unit 2") else ""
        params = (unit,) if where else ()
        agg = conn.execute(
            f"SELECT COUNT(*) AS events, COALESCE(SUM(duration_min), 0) AS total_min, COALESCE(SUM(spare_cost), 0) AS spare_cost FROM downtime_records {where}",
            params,
        ).fetchone()
        events = agg["events"]
        total_min = agg["total_min"]
        mttr = round(total_min / events, 1) if events else 0.0
        availability = round(100.0 - (total_min / (30 * 24 * 60) * 100.0), 2)
        return {"events": events, "total_min": total_min, "spare_cost": agg["spare_cost"], "mttr": mttr, "availability_pct": availability}


@app.get("/api/notifications")
def list_notifications():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM notifications ORDER BY created_at DESC").fetchall()]
