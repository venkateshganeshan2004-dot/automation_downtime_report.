-- TDConnex Automation Downtime & Unit-Separated Spare Inventory Schema

CREATE TABLE IF NOT EXISTS spare_parts (
    sku TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('Unit 1', 'Unit 2')),
    model TEXT NOT NULL,
    category TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    min_stock INTEGER NOT NULL DEFAULT 2,
    unit_cost REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sku, unit)
);

CREATE TABLE IF NOT EXISTS downtime_records (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('Unit 1', 'Unit 2')),
    equipment TEXT NOT NULL,
    shift TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('Red', 'Amber', 'Yellow')),
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    spare_sku TEXT,
    spare_model TEXT DEFAULT 'None',
    spare_qty INTEGER NOT NULL DEFAULT 0 CHECK (spare_qty >= 0),
    spare_cost REAL NOT NULL DEFAULT 0,
    problem_desc TEXT,
    root_cause TEXT NOT NULL,
    image_data TEXT,
    action_taken TEXT NOT NULL,
    technician TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pm_schedules (
    id TEXT PRIMARY KEY,
    unit TEXT NOT NULL CHECK (unit IN ('Unit 1', 'Unit 2')),
    equipment TEXT NOT NULL,
    task TEXT NOT NULL,
    frequency TEXT NOT NULL,
    due_date TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Due Soon' CHECK (status IN ('Overdue', 'Due Soon', 'Completed')),
    verified_by TEXT,
    verified_at TEXT
);

CREATE TABLE IF NOT EXISTS kaizens (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    area TEXT NOT NULL,
    category TEXT NOT NULL,
    owner TEXT NOT NULL,
    submitted_date TEXT NOT NULL,
    problem TEXT NOT NULL,
    countermeasure TEXT NOT NULL,
    before_image TEXT,
    after_image TEXT,
    saving TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Submitted' CHECK (stage IN ('Submitted', 'Under Review', 'Implemented'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('critical', 'warning', 'info')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('Unit 1', 'Unit 2')),
    priority TEXT NOT NULL CHECK (priority IN ('High', 'Medium', 'Low')),
    owner TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'In Progress', 'Completed'))
);
