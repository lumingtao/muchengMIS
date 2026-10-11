"""Encrypted local staging, independent of repair orders and their links."""
import json
from datetime import datetime, timedelta
from uuid import uuid4

from .legacy_client import FIELDS, LegacyError, digest


class LegacyCacheMixin:
    def cache_status(self, user):
        self.admin(user)
        source = self.source()
        state = self.one('SELECT * FROM legacy_cache_state WHERE source_id=?', (source['source_id'],)) or {}
        totals = self.one('SELECT COUNT(*) AS total,SUM(excluded) AS excluded,SUM(missing) AS missing FROM legacy_cache WHERE source_id=?', (source['source_id'],))
        job = self.one('SELECT * FROM legacy_fetch_jobs WHERE source_id=? ORDER BY rowid DESC LIMIT 1', (source['source_id'],))
        if job:
            job['result'] = json.loads(job.pop('result_json'))
        return state | totals | {'job': job, 'busy': bool(source['operation_token'])}

    def new_fetch(self, user, mode='incremental'):
        self.admin(user)
        if mode not in ('incremental', 'full'):
            raise LegacyError('拉取模式异常')
        job_id = uuid4().hex
        with self.write():
            source = self.source()
            if source['operation_token']:
                raise LegacyError('来源任务进行中，请稍后拉取')
            self.conn.execute('INSERT OR IGNORE INTO legacy_cache_state(source_id) VALUES(?)', (source['source_id'],))
            self.conn.execute('INSERT INTO legacy_fetch_jobs(job_id,source_id,mode,created_by) VALUES(?,?,?,?)', (job_id, source['source_id'], mode, user.username))
            self.conn.execute('UPDATE legacy_sources SET operation_token=? WHERE source_id=?', ('fetch:' + job_id, source['source_id']))
            self.audit(user, 'legacy:fetch_cache', job_id)
        return job_id

    def fetch_cache(self, job_id):
        job = self.one('SELECT * FROM legacy_fetch_jobs WHERE job_id=?', (job_id,))
        stats = {'received': 0, 'new': 0, 'changed': 0, 'unchanged': 0, 'missing': 0, 'phase': '连接来源'}
        try:
            source = self.source(job['source_id'])
            state = self.one('SELECT * FROM legacy_cache_state WHERE source_id=?', (source['source_id'],))
            client = self.client(source)
            full = job['mode'] == 'full' or not state['initialized']
            with self.write():
                self.conn.execute("UPDATE legacy_fetch_jobs SET status='reading',result_json=? WHERE job_id=?", (json.dumps(stats), job_id))
            columns = ','.join('"' + f + '"' for f in FIELDS)
            boundary = client.query('SELECT COUNT(*) AS n,COALESCE(MAX(rowid),0) AS boundary,COALESCE(MAX(datetime("更新时间")),\'\') AS watermark FROM "维修账单"')[0]
            stats.update(phase='分页读取并保存到本地', total=int(boundary['n']) if full else None)
            with self.write():
                self.conn.execute('UPDATE legacy_fetch_jobs SET result_json=? WHERE job_id=?', (json.dumps(stats), job_id))
            if not full and int(boundary['boundary']) < state['high_rowid']:
                raise LegacyError('来源行位置回退，可能恢复或替换了数据库；请先核对来源身份')
            seen = set()
            def store(page):
                with self.write():
                    for row in page:
                        rowid = int(row['__rowid'])
                        if rowid in seen:
                            continue
                        seen.add(rowid)
                        raw = {f: row[f] for f in FIELDS}
                        fingerprint = digest(raw)
                        existing = self.one('SELECT fingerprint FROM legacy_cache WHERE source_id=? AND source_rowid=?', (source['source_id'], rowid))
                        stats['received'] += 1
                        stats['new' if not existing else 'changed' if existing['fingerprint'] != fingerprint else 'unchanged'] += 1
                        self.conn.execute('''INSERT INTO legacy_cache(source_id,source_rowid,source_id_raw,snapshot_cipher,fingerprint)
                            VALUES(?,?,?,?,?) ON CONFLICT(source_id,source_rowid) DO UPDATE SET
                            source_id_raw=excluded.source_id_raw,snapshot_cipher=excluded.snapshot_cipher,
                            fingerprint=excluded.fingerprint,missing=0,observed_at=CURRENT_TIMESTAMP''',
                            (source['source_id'], rowid, None if raw['ID'] is None else str(raw['ID']), self.vault.encrypt(raw), fingerprint))
                    self.conn.execute('UPDATE legacy_fetch_jobs SET result_json=? WHERE job_id=?', (json.dumps(stats), job_id))
                    # Any partial successful page invalidates existing previews.
                    self.conn.execute('UPDATE legacy_cache_state SET revision=revision+1 WHERE source_id=?', (source['source_id'],))
            audit_cursor = state['audit_cursor']
            if full:
                client.progress = lambda *_: None
                client.page_receiver = store
                try:
                    rows = client._scan()
                finally:
                    client.progress = None
                    client.page_receiver = None
                stats['mode'] = 'initial' if not state['initialized'] else 'full'
            else:
                # Two-day overlap recovers delayed timestamp updates. A rolling
                # audit also detects edits/deletes whose timestamp never changes.
                since = ''
                if state['watermark']:
                    since = (datetime.strptime(state['watermark'], '%Y-%m-%d %H:%M:%S') - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
                last = 0
                while True:
                    clause = f'rowid>{int(state["high_rowid"])}'
                    if since:
                        clause += " OR datetime(\"更新时间\")>='" + since + "'"
                    page = client.query(f'SELECT rowid AS "__rowid",{columns} FROM "维修账单" WHERE rowid>{last} AND rowid<={int(boundary["boundary"])} AND ({clause}) ORDER BY rowid LIMIT 500')
                    if not page:
                        break
                    store(page)
                    last = int(page[-1]['__rowid'])
                stats['phase'] = '核验历史记录'
                with self.write():
                    self.conn.execute('UPDATE legacy_fetch_jobs SET result_json=? WHERE job_id=?', (json.dumps(stats), job_id))
                audit = self.rows('SELECT source_rowid FROM legacy_cache WHERE source_id=? AND source_rowid>? ORDER BY source_rowid LIMIT 500', (source['source_id'], audit_cursor))
                if not audit:
                    audit = self.rows('SELECT source_rowid FROM legacy_cache WHERE source_id=? ORDER BY source_rowid LIMIT 500', (source['source_id'],))
                keys = [r['source_rowid'] for r in audit]
                if keys:
                    page = client.query(f'SELECT rowid AS "__rowid",{columns} FROM "维修账单" WHERE rowid IN ({",".join(map(str, keys))}) ORDER BY rowid LIMIT 500')
                    store(page)
                    present = {int(r['__rowid']) for r in page}
                    with self.write():
                        for key in set(keys) - present:
                            self.conn.execute('UPDATE legacy_cache SET missing=1 WHERE source_id=? AND source_rowid=?', (source['source_id'], key))
                            stats['missing'] += 1
                    audit_cursor = max(keys)
                stats['mode'] = 'incremental'
            stats['phase'] = '完成'
            with self.write():
                if full:
                    for row in self.rows('SELECT source_rowid FROM legacy_cache WHERE source_id=? AND missing=0', (source['source_id'],)):
                        if row['source_rowid'] not in seen:
                            self.conn.execute('UPDATE legacy_cache SET missing=1 WHERE source_id=? AND source_rowid=?', (source['source_id'], row['source_rowid']))
                            stats['missing'] += 1
                self.conn.execute('UPDATE legacy_cache_state SET initialized=1,high_rowid=?,watermark=?,audit_cursor=?,revision=revision+1,fetched_at=CURRENT_TIMESTAMP WHERE source_id=?', (int(boundary['boundary']), boundary['watermark'], audit_cursor, source['source_id']))
                self.conn.execute("UPDATE legacy_fetch_jobs SET status='completed',error='',result_json=? WHERE job_id=?", (json.dumps(stats), job_id))
                self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE operation_token=?", ('fetch:' + job_id,))
        except Exception as exc:
            self.conn.rollback()
            with self.write():
                self.conn.execute("UPDATE legacy_fetch_jobs SET status='failed',error=? WHERE job_id=?", (str(exc) if isinstance(exc, LegacyError) else '暂存拉取失败；已收到的页面保留，增量游标未推进，可重试', job_id))
                self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE operation_token=?", ('fetch:' + job_id,))

    def cached_rows(self, source_id):
        return [self.vault.decrypt(r['snapshot_cipher']) | {'__rowid': r['source_rowid'], '__excluded': r['excluded'], '__missing': r['missing']} for r in self.rows('SELECT * FROM legacy_cache WHERE source_id=? ORDER BY source_rowid', (source_id,))]

    def cache_records(self, user, filters, q='', offset=0, limit=50, include_excluded=False):
        self.admin(user)
        rows = self.rows('SELECT * FROM legacy_cache WHERE source_id=? ORDER BY source_rowid DESC', (self.source()['source_id'],))
        selected = []
        for row in rows:
            raw = self.vault.decrypt(row.pop('snapshot_cipher'))
            if (row['excluded'] and not include_excluded) or not self.selected(raw, filters):
                continue
            if q and not any(q in str(raw[f] or '') for f in ('ID', '顾客', '机型', '工程师')):
                continue
            raw['锁屏密码'] = '••••••' if raw['锁屏密码'] else raw['锁屏密码']
            selected.append(row | {'raw': raw})
        return {'total': len(selected), 'items': selected[offset:offset + limit]}

    def manage_cache(self, user, rowid, data):
        self.admin(user)
        if set(data) - {'excluded', 'management_note'} or ('excluded' in data and type(data['excluded']) is not bool):
            raise LegacyError('暂存管理参数异常')
        if len(str(data.get('management_note', ''))) > 2000:
            raise LegacyError('管理备注最长 2000 字')
        with self.write():
            source = self.source()
            if source['operation_token']:
                raise LegacyError('来源任务进行中，请稍后管理')
            row = self.one('SELECT * FROM legacy_cache WHERE source_id=? AND source_rowid=?', (source['source_id'], rowid))
            if not row:
                raise LegacyError('暂存记录不存在')
            self.conn.execute('UPDATE legacy_cache SET excluded=?,management_note=? WHERE source_id=? AND source_rowid=?', (int(data.get('excluded', row['excluded'])), data.get('management_note', row['management_note']), source['source_id'], rowid))
            self.conn.execute('UPDATE legacy_cache_state SET revision=revision+1 WHERE source_id=?', (source['source_id'],))
            self.audit(user, 'legacy:manage_cache', rowid)
        return {'ok': True}

    def refresh_cache_row(self, user, rowid):
        self.admin(user)
        token = 'refresh:' + uuid4().hex
        with self.write():
            source = self.source()
            if source['operation_token']:
                raise LegacyError('来源任务进行中，请稍后刷新')
            row = self.one('SELECT * FROM legacy_cache WHERE source_id=? AND source_rowid=?', (source['source_id'], rowid))
            if not row:
                raise LegacyError('暂存记录不存在')
            self.conn.execute('UPDATE legacy_sources SET operation_token=? WHERE source_id=?', (token, source['source_id']))
        try:
            client = self.client(source)
            columns = ','.join('"' + f + '"' for f in FIELDS)
            page = client.query(f'SELECT rowid AS "__rowid",{columns} FROM "维修账单" WHERE rowid={int(rowid)} LIMIT 1')
            with self.write():
                if page:
                    raw = {f: page[0][f] for f in FIELDS}
                    if str(raw['ID']) != str(row['source_id_raw']):
                        raise LegacyError('来源行的账单身份已改变，请人工核对后全量检查')
                    self.conn.execute('UPDATE legacy_cache SET snapshot_cipher=?,fingerprint=?,missing=0,observed_at=CURRENT_TIMESTAMP WHERE source_id=? AND source_rowid=?', (self.vault.encrypt(raw), digest(raw), source['source_id'], rowid))
                else:
                    self.conn.execute('UPDATE legacy_cache SET missing=1 WHERE source_id=? AND source_rowid=?', (source['source_id'], rowid))
                self.conn.execute('UPDATE legacy_cache_state SET revision=revision+1 WHERE source_id=?', (source['source_id'],))
                self.audit(user, 'legacy:refresh_cache_row', rowid)
            return {'ok': True}
        finally:
            with self.write():
                self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE operation_token=?", (token,))
