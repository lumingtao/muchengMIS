"""Additive legacy import schema. No migration of existing business records."""
SCHEMA = """
CREATE TABLE IF NOT EXISTS legacy_sources (
 source_id TEXT PRIMARY KEY, base_url TEXT NOT NULL, store_key TEXT NOT NULL DEFAULT 'wuxi',
 username TEXT NOT NULL, password_cipher TEXT NOT NULL, mappings_json TEXT NOT NULL DEFAULT '{}',
 version INTEGER NOT NULL DEFAULT 1, operation_token TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS legacy_records (
 record_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL REFERENCES legacy_sources(source_id),
 source_table TEXT NOT NULL DEFAULT '维修账单', source_id_raw TEXT NOT NULL,
 snapshot_cipher TEXT NOT NULL, fingerprint TEXT NOT NULL, observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 missing INTEGER NOT NULL DEFAULT 0, UNIQUE(source_id, source_table, source_id_raw)
);
CREATE TABLE IF NOT EXISTS legacy_links (
 record_id INTEGER PRIMARY KEY REFERENCES legacy_records(record_id),
 repair_order_id INTEGER NOT NULL UNIQUE REFERENCES repair_orders(repair_order_id),
 machine_id INTEGER NOT NULL REFERENCES machines(machine_id), customer_id INTEGER REFERENCES customers(customer_id),
 ownership TEXT NOT NULL DEFAULT 'following' CHECK(ownership IN ('following','taken')),
 classification TEXT NOT NULL DEFAULT 'unknown' CHECK(classification IN ('active','history','unknown')),
 taken_by TEXT NOT NULL DEFAULT '', taken_at TEXT NOT NULL DEFAULT '', taken_stage TEXT NOT NULL DEFAULT '',
 applied_fingerprint TEXT NOT NULL DEFAULT '', amounts_json TEXT NOT NULL DEFAULT '{}',
 parts_json TEXT NOT NULL DEFAULT '[]', original_engineer TEXT NOT NULL DEFAULT '',
 original_payment TEXT NOT NULL DEFAULT '', initial_due TEXT, initial_paid TEXT,
 synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS legacy_batches (
 batch_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES legacy_sources(source_id),
 status TEXT NOT NULL, filters_json TEXT NOT NULL, source_version INTEGER NOT NULL,
 profile_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT NOT NULL DEFAULT '', backup_path TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS legacy_batch_items (
 item_id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL REFERENCES legacy_batches(batch_id),
 source_id_raw TEXT, row_key TEXT NOT NULL, snapshot_cipher TEXT NOT NULL,
 fingerprint TEXT NOT NULL, target_fingerprint TEXT NOT NULL DEFAULT '',
 action TEXT NOT NULL, result TEXT NOT NULL DEFAULT 'pending', reason TEXT NOT NULL DEFAULT '',
 before_cipher TEXT NOT NULL DEFAULT '', repair_order_id INTEGER,
 UNIQUE(batch_id, row_key)
);
CREATE TABLE IF NOT EXISTS legacy_attachments (
 attachment_id INTEGER PRIMARY KEY AUTOINCREMENT, record_id INTEGER NOT NULL REFERENCES legacy_records(record_id),
 reference TEXT NOT NULL, reference_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 content_hash TEXT NOT NULL DEFAULT '', photo_id INTEGER REFERENCES repair_order_photos(photo_id),
 error TEXT NOT NULL DEFAULT '', UNIQUE(record_id, reference_hash)
);
CREATE INDEX IF NOT EXISTS idx_legacy_batches_source ON legacy_batches(source_id,created_at);
CREATE INDEX IF NOT EXISTS idx_legacy_items_batch ON legacy_batch_items(batch_id,result);
CREATE TABLE IF NOT EXISTS legacy_cache (
 source_id TEXT NOT NULL REFERENCES legacy_sources(source_id), source_rowid INTEGER NOT NULL,
 source_id_raw TEXT, snapshot_cipher TEXT NOT NULL, fingerprint TEXT NOT NULL,
 missing INTEGER NOT NULL DEFAULT 0, excluded INTEGER NOT NULL DEFAULT 0,
 management_note TEXT NOT NULL DEFAULT '', observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_id,source_rowid)
);
CREATE INDEX IF NOT EXISTS idx_legacy_cache_identity ON legacy_cache(source_id,source_id_raw);
CREATE TABLE IF NOT EXISTS legacy_cache_state (
 source_id TEXT PRIMARY KEY REFERENCES legacy_sources(source_id), initialized INTEGER NOT NULL DEFAULT 0,
 high_rowid INTEGER NOT NULL DEFAULT 0, watermark TEXT NOT NULL DEFAULT '', audit_cursor INTEGER NOT NULL DEFAULT 0,
 revision INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS legacy_fetch_jobs (
 job_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES legacy_sources(source_id),
 mode TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', result_json TEXT NOT NULL DEFAULT '{}',
 error TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def migrate_legacy(conn):
    conn.executescript(SCHEMA)
    if 'taken_stage' not in {row[1] for row in conn.execute('PRAGMA table_info(legacy_links)')}:
        conn.execute("ALTER TABLE legacy_links ADD COLUMN taken_stage TEXT NOT NULL DEFAULT ''")
    # Reuse previously fetched preview snapshots without creating business rows.
    # These may cover only a date range, so keep initialized=0 until first pull.
    conn.execute('INSERT OR IGNORE INTO legacy_cache_state(source_id) SELECT source_id FROM legacy_sources')
    conn.execute('''INSERT OR IGNORE INTO legacy_cache(source_id,source_rowid,source_id_raw,snapshot_cipher,fingerprint)
        SELECT b.source_id,CAST(i.row_key AS INTEGER),i.source_id_raw,i.snapshot_cipher,i.fingerprint
        FROM legacy_batch_items i JOIN legacy_batches b ON b.batch_id=i.batch_id
        JOIN legacy_cache_state s ON s.source_id=b.source_id
        WHERE s.initialized=0 AND i.row_key<>'' AND i.row_key NOT GLOB '*[^0-9]*'
        AND i.item_id=(SELECT MAX(ii.item_id) FROM legacy_batch_items ii JOIN legacy_batches bb ON bb.batch_id=ii.batch_id
          WHERE bb.source_id=b.source_id AND ii.row_key=i.row_key)''')
    # Protect every SQL write path, including future endpoints. The import service
    # enables this connection-local capability only inside its own transactions.
    guarded = {
        'repair_orders': ('repair_order_id', 'repair_order_id'),
        'machines': ('machine_id', 'machine_id'),
        'repair_items': ('repair_order_id', 'repair_order_id'),
        'repair_income_items': ('repair_order_id', 'repair_order_id'),
        'repair_cost_items': ('repair_order_id', 'repair_order_id'),
        'repair_order_inspections': ('repair_order_id', 'repair_order_id'),
        'repair_order_notes': ('repair_order_id', 'repair_order_id'),
        'repair_order_photos': ('repair_order_id', 'repair_order_id'),
        'repair_materials': ('repair_order_id', 'repair_order_id'),
        'repair_material_reservations': ('repair_order_id', 'repair_order_id'),
        'receivables': ('repair_order_id', 'repair_order_id'),
        'material_requests': ('repair_order_id', 'repair_order_id'),
        'material_returns': ('repair_order_id', 'repair_order_id'),
        'stock_movements': ('repair_order_id', 'repair_order_id'),
        'material_units': ('repair_order_id', 'repair_order_id'),
        'payments': ('source_id', 'repair_order_id'),
    }
    for table, (column, link_column) in guarded.items():
        for operation in ('INSERT', 'UPDATE', 'DELETE'):
            images = ['NEW'] if operation == 'INSERT' else ['OLD'] if operation == 'DELETE' else ['OLD', 'NEW']
            conditions = []
            for image in images:
                repair_only = f"{image}.source_type='repair' AND " if table == 'payments' else ''
                conditions.append(f"({repair_only}EXISTS(SELECT 1 FROM legacy_links l WHERE l.{link_column}={image}.{column} AND l.ownership='following'))")
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS legacy_guard_{table}_{operation.lower()}
                BEFORE {operation} ON {table}
                WHEN legacy_import_write()=0 AND ({' OR '.join(conditions)})
                BEGIN SELECT RAISE(ABORT, '老系统工单需要先接管'); END""")
