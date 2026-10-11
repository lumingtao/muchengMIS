from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from .config import ROOT_DIR
from .legacy_client import FIELDS, LegacyClient, LegacyError, digest, validate_url
from .models import Role, User, OrderStatus
from .repository import Repository
from .legacy_cache import LegacyCacheMixin

logger = logging.getLogger(__name__)
STATE_RULE_VERSION = '2026-10-10-confirmed-miniapp-flow'


def applied_state_fingerprint(raw, source_version):
    parts = [digest(raw), source_version]
    # Only the two corrected combinations need an update for unchanged source data.
    if str(raw.get('付款方式') or '').strip() == '待维修' and str(raw.get('备注') or '').strip() in ('待结账', '维修完成'):
        parts.append(STATE_RULE_VERSION)
    return digest(parts)


def pack(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def amount(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or abs(number) > Decimal('1000000000') or number != number.quantize(Decimal('.01')):
            raise InvalidOperation
        return str(number)
    except InvalidOperation:
        raise LegacyError('金额格式异常') from None


def image_references(value):
    if not value:
        return []
    if isinstance(value, list):
        values = value
    else:
        text = str(value).strip()
        if text.startswith('['):
            try:
                values = json.loads(text)
            except ValueError:
                raise LegacyError('图片引用 JSON 格式异常') from None
            if not isinstance(values, list):
                raise LegacyError('图片引用需要为列表')
        else:
            values = text.replace('\r', '').replace(';', '\n').split('\n')
    if any(not isinstance(v, str) for v in values):
        raise LegacyError('图片引用含非文本值，需要人工核对')
    return list(dict.fromkeys(v.strip() for v in values if v.strip()))


class Vault:
    def __init__(self, database_path):
        supplied = os.getenv('MIS_LEGACY_KEY')
        if supplied:
            key = supplied.encode()
        else:
            path = Path(database_path).with_suffix('.legacy.key')
            if not path.exists():
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(Fernet.generate_key())
                except FileExistsError:
                    pass
            key = path.read_bytes()
        self.fernet = Fernet(key)

    def encrypt(self, value):
        return self.fernet.encrypt(pack(value).encode()).decode()

    def decrypt(self, value):
        try:
            return json.loads(self.fernet.decrypt(value.encode()))
        except (InvalidToken, ValueError):
            raise LegacyError('导入加密密钥不匹配，请恢复原密钥') from None


class LegacyImportService(LegacyCacheMixin):
    def __init__(self, conn, vault=None, client_factory=LegacyClient):
        self.conn = conn
        self.repo = Repository(conn)
        self.database_path = conn.execute('PRAGMA database_list').fetchone()['file']
        self.vault = vault or Vault(self.database_path)
        self.client_factory = client_factory

    def admin(self, user):
        if user.role not in (Role.admin, Role.boss):
            raise PermissionError('仅管理员或老板可管理老系统导入')

    def one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def rows(self, sql, params=()):
        return [dict(row) for row in self.conn.execute(sql, params)]

    @contextmanager
    def write(self):
        self.conn.execute('BEGIN IMMEDIATE')
        self.conn.create_function('legacy_import_write', 0, lambda: 1)
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self.conn.create_function('legacy_import_write', 0, lambda: 0)

    def audit(self, user, action, target):
        self.conn.execute("INSERT INTO operation_logs(username,role,action,target_type,target_id,result) VALUES(?,?,?,?,?,'成功')", (user.username, str(user.role), action, 'legacy_import', str(target)))

    def source(self, source_id='wuxi-legacy'):
        source = self.one('SELECT * FROM legacy_sources WHERE source_id=?', (source_id,))
        if not source:
            raise LegacyError('请先配置老系统连接')
        return source

    def public_source(self, user):
        self.admin(user)
        source = self.one('SELECT * FROM legacy_sources WHERE source_id=?', ('wuxi-legacy',))
        if not source:
            return None
        return {k: source[k] for k in ('source_id', 'base_url', 'store_key', 'username', 'version')} | {'configured': True, 'mappings': json.loads(source['mappings_json']), 'busy': bool(source['operation_token'])}

    def save_source(self, user, data):
        self.admin(user)
        base = validate_url(str(data.get('base_url', '')))
        username = str(data.get('username', '')).strip()
        if not username or data.get('store_key', 'wuxi') != 'wuxi':
            raise LegacyError('第一版仅支持无锡库，且需要登录账号')
        with self.write():
            old = self.one('SELECT * FROM legacy_sources WHERE source_id=?', ('wuxi-legacy',))
            if old and old['operation_token']:
                raise LegacyError('来源正在读取或同步，稍后再修改配置')
            if old and old['base_url'] != base:
                raise LegacyError('已配置来源地址不可替换；数据库替换需要先核对来源身份')
            password = data.get('password')
            if not old and not password:
                raise LegacyError('首次配置需要密码')
            cipher = self.vault.encrypt(password) if password else old['password_cipher']
            self.conn.execute("""INSERT INTO legacy_sources(source_id,base_url,username,password_cipher)
                VALUES('wuxi-legacy',?,?,?) ON CONFLICT(source_id) DO UPDATE SET
                username=excluded.username,password_cipher=excluded.password_cipher,version=version+1""", (base, username, cipher))
            self.audit(user, 'legacy:configure', 'wuxi-legacy')
        return self.public_source(user)

    def client(self, source):
        return self.client_factory(source['base_url'], source['username'], self.vault.decrypt(source['password_cipher']), source['store_key'])

    def test_connection(self, user):
        self.admin(user)
        client = self.client(self.source())
        columns = client.query('SELECT name FROM pragma_table_info("维修账单")')
        if not set(FIELDS).issubset({r['name'] for r in columns}):
            raise LegacyError('老系统维修账单字段不完整')
        return {'ok': True, 'fields': FIELDS, 'count': client.query('SELECT COUNT(*) AS n FROM "维修账单"')[0]['n']}

    def mappings(self, user, data):
        self.admin(user)
        if set(data) - {'engineers', 'states'} or not isinstance(data.get('engineers', {}), dict) or not isinstance(data.get('states', {}), dict):
            raise LegacyError('映射格式异常')
        for username in data.get('engineers', {}).values():
            employee = self.one('SELECT e.employee_id FROM employees e JOIN users u ON u.username=e.username WHERE e.username=? AND u.enabled=1', (username,))
            if not employee:
                raise LegacyError('工程师映射需要指向有效员工账号')
        for state in data.get('states', {}).values():
            if not isinstance(state, dict) or state.get('classification') not in ('active', 'history', 'unknown') or state.get('status') not in {s.value for s in OrderStatus}:
                raise LegacyError('状态映射需要指定分类和有效工单状态')
        with self.write():
            source = self.source()
            if source['operation_token']:
                raise LegacyError('来源任务进行中，请稍后修改映射')
            self.conn.execute('UPDATE legacy_sources SET mappings_json=?,version=version+1 WHERE source_id=?', (pack(data), source['source_id']))
            self.audit(user, 'legacy:mappings', source['source_id'])
        return self.public_source(user)

    def normalize(self, raw, mappings):
        issues = []
        amounts = {}
        for field in ('报价', '成本', '利润', '人工费'):
            try:
                amounts[field] = amount(raw[field])
                if field != '利润' and amounts[field] is not None and Decimal(amounts[field]) < 0:
                    issues.append(field + '为负数，需要确认')
            except LegacyError:
                amounts[field] = None
                issues.append(field + '金额格式异常')
        remark, payment = str(raw['备注'] or '').strip(), str(raw['付款方式'] or '').strip()
        key = remark + '|' + payment
        classification, status = 'unknown', '已开单'
        if payment == '待维修' and remark == '维修完成':
            # Order 20436: confirming payment sets 备注, leaving 付款方式 unchanged.
            classification, status = 'history', '已结单'
        elif payment == '待维修' and remark == '待结账':
            classification, status = 'active', '已交付'
        elif payment == '已结账/已取机' and remark == '维修完成':
            classification, status = 'history', '已结单'
        elif remark in ('接机', '待检测', '待维修'):
            classification, status = 'active', '已开单'
        elif remark in ('检测中',):
            classification, status = 'active', '检测中'
        elif remark in ('维修中', '处理中'):
            classification, status = 'active', '处理中'
        elif remark in ('维修完成', '待取机') and payment not in ('已结账/已取机',):
            classification, status = 'active', '待交付'
        override = mappings.get('states', {}).get(key)
        if override:
            classification, status = override['classification'], override['status']
        if classification == 'unknown':
            issues.append('状态组合需要映射或确认')
        if payment == '已结账/已取机' and classification != 'history':
            issues.append('取机结账标记与维修阶段存在矛盾')
        engineer = str(raw['工程师'] or '').strip()
        assigned = mappings.get('engineers', {}).get(engineer, '')
        if engineer and not assigned:
            issues.append('工程师尚未映射，接管前确认')
        try:
            references = image_references(raw['图片'])
        except LegacyError as exc:
            references = []
            issues.append(str(exc))
        created = ''
        if raw['时间']:
            try:
                created = datetime.fromisoformat(str(raw['时间']).replace('T', ' ')).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                issues.append('开单时间格式异常')
        parts = [{'position': i, 'name': raw[f'配件{i}'], 'source': raw['配件来源']} for i in range(1, 4)]
        return {'classification': classification, 'status': status, 'assigned': assigned, 'created': created, 'amounts': amounts, 'parts': parts, 'references': references, 'issues': issues}

    def target_hash(self, order_id):
        if not order_id:
            return ''
        order = self.one('SELECT * FROM repair_orders WHERE repair_order_id=?', (order_id,))
        if not order:
            return 'missing'
        value = {'order': order, 'machine': self.one('SELECT * FROM machines WHERE machine_id=?', (order['machine_id'],)), 'link': self.one('SELECT * FROM legacy_links WHERE repair_order_id=?', (order_id,))}
        for table in ('repair_items', 'payments', 'repair_order_notes', 'repair_order_inspections', 'repair_material_reservations'):
            clause = "source_type='repair' AND source_id=?" if table == 'payments' else 'repair_order_id=?'
            value[table] = self.rows(f'SELECT * FROM {table} WHERE {clause} ORDER BY rowid', (order_id,))
        return digest(value)

    def selected(self, raw, filters):
        if filters.get('ids') and str(raw['ID']) not in filters['ids']:
            return False
        day = str(raw.get('时间') or '')[:10]
        return not ((filters.get('date_from') and day < filters['date_from']) or (filters.get('date_to') and day > filters['date_to']))

    def new_batch(self, user, filters):
        self.admin(user)
        if set(filters) - {'ids', 'date_from', 'date_to'}:
            raise LegacyError('筛选条件异常')
        if 'ids' in filters and (not isinstance(filters['ids'], list) or any(not isinstance(x, str) for x in filters['ids'])):
            raise LegacyError('旧账单 ID 需要为文本列表')
        for key in ('date_from', 'date_to'):
            if filters.get(key):
                try:
                    datetime.strptime(filters[key], '%Y-%m-%d')
                except (ValueError, TypeError):
                    raise LegacyError('日期需要为 YYYY-MM-DD') from None
        if filters.get('date_from') and filters.get('date_to') and filters['date_from'] > filters['date_to']:
            raise LegacyError('开始日期晚于结束日期')
        batch_id = uuid4().hex
        with self.write():
            source = self.source()
            if source['operation_token']:
                raise LegacyError('该来源已有任务进行中')
            self.conn.execute('UPDATE legacy_sources SET operation_token=? WHERE source_id=?', (batch_id, source['source_id']))
            self.conn.execute("INSERT INTO legacy_batches(batch_id,source_id,status,filters_json,source_version,created_by) VALUES(?,?,'queued',?,?,?)", (batch_id, source['source_id'], pack(filters), source['version'], user.username))
            self.audit(user, 'legacy:preview', batch_id)
        return batch_id

    def fail_job(self, batch_id, message):
        self.conn.rollback()
        with self.write():
            self.conn.execute("UPDATE legacy_batches SET status='failed',error=?,completed_at=CURRENT_TIMESTAMP WHERE batch_id=?", (message, batch_id))
            self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE operation_token=?", (batch_id,))

    def preview(self, batch_id):
        try:
            batch = self.one('SELECT * FROM legacy_batches WHERE batch_id=?', (batch_id,))
            source = self.source(batch['source_id'])
            with self.write():
                self.conn.execute("UPDATE legacy_batches SET status='reading' WHERE batch_id=?", (batch_id,))
            state = self.one('SELECT * FROM legacy_cache_state WHERE source_id=?', (source['source_id'],))
            if not state or not state['initialized']:
                raise LegacyError('请先拉取到本地暂存库，再进行本地筛选预览')
            cached = self.cached_rows(source['source_id'])
            all_rows = [r for r in cached if not r['__missing']]
            ids = Counter(str(r['ID']) for r in all_rows)
            filters, mappings = json.loads(batch['filters_json']), json.loads(source['mappings_json'])
            states = Counter(str(r['备注'] or '') + '|' + str(r['付款方式'] or '') for r in all_rows)
            engineers = Counter(str(r['工程师'] or '') for r in all_rows)
            serials = Counter(str(r['串号'] or '') for r in all_rows)
            profile = {'source_count': len(all_rows), 'duplicate_ids': {k: v for k, v in ids.items() if v > 1}, 'empty_ids': sum(v for k, v in ids.items() if not k.strip() or k == 'None'), 'state_combinations': dict(states), 'engineers': dict(engineers), 'duplicate_serials': {k: v for k, v in serials.items() if k and v > 1}, 'full_scan': not any(filters.values()), 'issues': {}}
            profile['cache_revision'] = state['revision']
            profile['state_rule_version'] = STATE_RULE_VERSION
            with self.write():
                for row in all_rows:
                    if row['__excluded'] or not self.selected(row, filters):
                        continue
                    raw = {field: row[field] for field in FIELDS}
                    old_id = str(raw['ID'])
                    record = self.one('SELECT r.*,l.repair_order_id,l.ownership,l.applied_fingerprint FROM legacy_records r LEFT JOIN legacy_links l ON l.record_id=r.record_id WHERE source_id=? AND source_id_raw=?', (source['source_id'], old_id))
                    fingerprint = digest(raw)
                    normalized = self.normalize(raw, mappings)
                    action, reason = 'new', '; '.join(normalized['issues'])
                    if raw['ID'] is None or not old_id.strip() or ids[old_id] > 1:
                        action, reason = 'invalid', '旧账单 ID 为空或重复'
                    elif record and record['repair_order_id']:
                        if record['ownership'] == 'taken':
                            action = 'taken_changed' if record['fingerprint'] != fingerprint else 'unchanged'
                        else:
                            action = 'unchanged' if record['applied_fingerprint'] == applied_state_fingerprint(raw, source['version']) else 'update'
                    if action not in ('invalid', 'taken_changed', 'unchanged') and (normalized['classification'] == 'unknown' or any('金额' in issue or '为负数' in issue or '矛盾' in issue for issue in normalized['issues'])):
                        action = 'review'
                    for issue in normalized['issues']:
                        profile['issues'][issue] = profile['issues'].get(issue, 0) + 1
                    target_id = record.get('repair_order_id') if record else None
                    self.conn.execute('''INSERT INTO legacy_batch_items(batch_id,source_id_raw,row_key,snapshot_cipher,fingerprint,target_fingerprint,action,reason,repair_order_id)
                        VALUES(?,?,?,?,?,?,?,?,?)''', (batch_id, old_id, str(row['__rowid']), self.vault.encrypt(raw), fingerprint, self.target_hash(target_id), action, reason, target_id))
                if profile['full_scan']:
                    present = {str(r['ID']) for r in all_rows if r['ID'] is not None}
                    for record in self.rows('SELECT * FROM legacy_records WHERE source_id=?', (source['source_id'],)):
                        if record['source_id_raw'] not in present:
                            self.conn.execute('''INSERT INTO legacy_batch_items(batch_id,source_id_raw,row_key,snapshot_cipher,fingerprint,action,reason)
                                VALUES(?,?,?,?,?,'missing','完整扫描中来源记录缺失')''', (batch_id, record['source_id_raw'], 'missing:' + str(record['record_id']), record['snapshot_cipher'], record['fingerprint']))
                self.conn.execute("UPDATE legacy_batches SET status='preview',profile_json=? WHERE batch_id=?", (pack(profile), batch_id))
                self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE source_id=?", (source['source_id'],))
        except Exception as exc:
            if not isinstance(exc, LegacyError):
                logger.exception('Legacy preview job failed: %s', batch_id)
            self.fail_job(batch_id, str(exc) if isinstance(exc, LegacyError) else '读取预览失败，请检查来源及服务日志')

    def batch(self, user, batch_id):
        self.admin(user)
        result = self.one('SELECT * FROM legacy_batches WHERE batch_id=?', (batch_id,))
        if not result:
            raise LegacyError('同步批次不存在')
        result['profile'] = json.loads(result.pop('profile_json'))
        result['filters'] = json.loads(result.pop('filters_json'))
        result['counts'] = self.rows('SELECT action,result,COUNT(*) AS count FROM legacy_batch_items WHERE batch_id=? GROUP BY action,result', (batch_id,))
        result['total'] = sum(r['count'] for r in result['counts'])
        selected = [r for r in result['counts'] if r['result'] != 'skipped']
        result['progress'] = {'total': sum(r['count'] for r in selected), 'done': sum(r['count'] for r in selected if r['result'] != 'pending')}
        return result

    def batches(self, user):
        self.admin(user)
        return self.rows('SELECT batch_id,status,error,created_at,completed_at FROM legacy_batches ORDER BY rowid DESC LIMIT 100')

    def items(self, user, batch_id, offset=0, limit=100):
        self.admin(user)
        return self.rows('SELECT item_id,source_id_raw,action,result,reason,repair_order_id FROM legacy_batch_items WHERE batch_id=? ORDER BY item_id LIMIT ? OFFSET ?', (batch_id, limit, offset))

    def item_detail(self, user, item_id):
        self.admin(user)
        item = self.one('SELECT * FROM legacy_batch_items WHERE item_id=?', (item_id,))
        if not item:
            raise LegacyError('预览记录不存在')
        batch = self.one('SELECT source_id FROM legacy_batches WHERE batch_id=?', (item['batch_id'],))
        record = self.one('SELECT * FROM legacy_records WHERE source_id=? AND source_id_raw=?', (batch['source_id'], item['source_id_raw']))
        raw = self.vault.decrypt(item.pop('snapshot_cipher'))
        if item['before_cipher']:
            old = self.vault.decrypt(item['before_cipher'])
        elif item['result'] == 'success' and item['action'] == 'new':
            old = {}
        else:
            old = self.vault.decrypt(record['snapshot_cipher']) if record else {}
        for value in (raw, old):
            if '锁屏密码' in value:
                value['锁屏密码'] = '••••••' if value['锁屏密码'] else value['锁屏密码']
        item.pop('before_cipher')
        return item | {'raw': raw, 'previous': old, 'diff': {k: {'old': old.get(k), 'new': raw[k]} for k in FIELDS if old.get(k) != raw[k]}, 'target': self.one('SELECT order_no,status,customer_name FROM repair_orders WHERE repair_order_id=?', (item['repair_order_id'],)) if item['repair_order_id'] else None}

    def queue_execution(self, user, batch_id, retry=False, item_ids=None):
        self.admin(user)
        with self.write():
            batch = self.one('SELECT * FROM legacy_batches WHERE batch_id=?', (batch_id,))
            if not batch or batch['status'] not in ('preview', 'partial', 'interrupted', 'failed'):
                raise LegacyError('该批次当前不支持执行，请刷新预览')
            if 'full_scan' not in json.loads(batch['profile_json']):
                raise LegacyError('该批次未完成读取预览，请重新读取')
            source = self.source(batch['source_id'])
            profile = json.loads(batch['profile_json'])
            if profile.get('state_rule_version') != STATE_RULE_VERSION:
                raise LegacyError('状态识别规则已更新，请重新生成预览')
            if 'cache_revision' not in profile:
                raise LegacyError('旧批次请从本地暂存库重新生成预览')
            state = self.one('SELECT revision FROM legacy_cache_state WHERE source_id=?', (source['source_id'],))
            if not state or state['revision'] != profile['cache_revision']:
                raise LegacyError('本地暂存数据已变化，请重新生成预览')
            if not retry:
                if not isinstance(item_ids, list) or not item_ids or any(type(i) is not int for i in item_ids):
                    raise LegacyError('请明确勾选要同步到订单系统的记录')
                valid = {r['item_id'] for r in self.items(user, batch_id, 0, 1000000)}
                if set(item_ids) - valid:
                    raise LegacyError('选择的记录不属于本批次')
                for item in valid - set(item_ids):
                    self.conn.execute("UPDATE legacy_batch_items SET result='skipped' WHERE item_id=?", (item,))
            if source['version'] != batch['source_version']:
                raise LegacyError('来源配置或映射已修改，请重新预览')
            if source['operation_token']:
                raise LegacyError('该来源已有任务进行中')
            self.conn.execute('UPDATE legacy_sources SET operation_token=? WHERE source_id=?', (batch_id, source['source_id']))
            self.conn.execute("UPDATE legacy_batches SET status='queued_execute',error='' WHERE batch_id=?", (batch_id,))
            self.audit(user, 'legacy:retry' if retry else 'legacy:execute', batch_id)

    def backup(self, batch_id):
        directory = Path(self.database_path).parent / 'legacy_backups'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8] + '.sqlite3')
        with sqlite3.connect(self.database_path) as source, sqlite3.connect(path) as destination:
            source.backup(destination)
        with self.write():
            self.conn.execute('UPDATE legacy_batches SET backup_path=? WHERE batch_id=?', (str(path), batch_id))

    def execute(self, batch_id):
        try:
            batch = self.one('SELECT * FROM legacy_batches WHERE batch_id=?', (batch_id,))
            source = self.source(batch['source_id'])
            if json.loads(batch['profile_json']).get('state_rule_version') != STATE_RULE_VERSION:
                raise LegacyError('状态识别规则已更新，请重新生成预览')
            client = self.client(source)
            state = self.one('SELECT revision FROM legacy_cache_state WHERE source_id=?', (source['source_id'],))
            if state['revision'] != json.loads(batch['profile_json'])['cache_revision']:
                raise LegacyError('暂存数据已变化，请重新预览')
            scanned = [r for r in self.cached_rows(source['source_id']) if not r['__missing']]
            current = {}
            duplicates = set()
            for row in scanned:
                old_id = str(row['ID'])
                if old_id in current:
                    duplicates.add(old_id)
                current[old_id] = {f: row[f] for f in FIELDS}
            self.backup(batch_id)
            with self.write():
                self.conn.execute("UPDATE legacy_batches SET status='executing' WHERE batch_id=?", (batch_id,))
            mappings = json.loads(source['mappings_json'])
            items = self.rows("SELECT * FROM legacy_batch_items WHERE batch_id=? AND result NOT IN ('success','skipped') ORDER BY item_id", (batch_id,))
            latest_page = {}
            for position, item in enumerate(items):
                if position % 500 == 0:
                    keys = [int(i['row_key']) for i in items[position:position+500] if i['row_key'].isdigit()]
                    latest_page = {}
                    if keys:
                        columns = ','.join('"'+f+'"' for f in FIELDS)
                        latest_rows = client.query(f'SELECT rowid AS "__rowid",{columns} FROM "维修账单" WHERE rowid IN ({",".join(map(str, keys))}) ORDER BY rowid LIMIT 500')
                        identities = {str(row['ID']) for row in latest_rows if row['ID'] is not None}
                        if identities:
                            literals = ','.join("'" + identity.replace("'", "''") + "'" for identity in identities)
                            duplicate_rows = client.query(f'SELECT "ID" FROM "维修账单" WHERE "ID" IN ({literals}) GROUP BY "ID" HAVING COUNT(*)>1 LIMIT 500')
                            duplicates.update(str(row['ID']) for row in duplicate_rows)
                        latest_page = {str(r['__rowid']): {f: r[f] for f in FIELDS} for r in latest_rows}
                try:
                    with self.write():
                        if item['action'] in ('invalid', 'review'):
                            self.conn.execute("UPDATE legacy_batch_items SET result='blocked' WHERE item_id=?", (item['item_id'],))
                            continue
                        raw = current.get(item['source_id_raw'])
                        if item['action'] == 'missing':
                            literal = str(item['source_id_raw']).replace("'", "''")
                            if client.query(f'SELECT "ID" FROM "维修账单" WHERE "ID"=\'{literal}\' LIMIT 1'):
                                raise LegacyError('来源记录已重新出现，请先增量拉取并重新预览')
                            if raw is not None:
                                raise LegacyError('来源记录已重新出现，请重新预览')
                            self.conn.execute('UPDATE legacy_records SET missing=1,observed_at=CURRENT_TIMESTAMP WHERE source_id=? AND source_id_raw=?', (source['source_id'], item['source_id_raw']))
                        else:
                            if not raw or item['source_id_raw'] in duplicates or digest(raw) != item['fingerprint']:
                                raise LegacyError('来源记录已变化，请重新预览')
                            # Refresh each page immediately before committing rows;
                            # remote reads happen outside the local write transaction.
                            latest = latest_page.get(item['row_key'])
                            if latest is None or digest(latest) != item['fingerprint']:
                                raise LegacyError('来源记录已变化，请重新预览')
                            record = self.one('SELECT * FROM legacy_records WHERE source_id=? AND source_id_raw=?', (source['source_id'], item['source_id_raw']))
                            link = self.one('SELECT * FROM legacy_links WHERE record_id=?', (record['record_id'],)) if record else None
                            if link and link['repair_order_id'] != item['repair_order_id']:
                                raise LegacyError('对应关系已变化，请重新预览')
                            if (not link or link['ownership'] == 'following') and self.target_hash(item['repair_order_id']) != item['target_fingerprint']:
                                raise LegacyError('目标工单已变化，请重新预览')
                            if record:
                                self.conn.execute('UPDATE legacy_batch_items SET before_cipher=? WHERE item_id=?', (record['snapshot_cipher'], item['item_id']))
                                self.conn.execute('UPDATE legacy_records SET snapshot_cipher=?,fingerprint=?,observed_at=CURRENT_TIMESTAMP,missing=0 WHERE record_id=?', (self.vault.encrypt(raw), item['fingerprint'], record['record_id']))
                                record_id = record['record_id']
                            else:
                                record_id = self.conn.execute('INSERT INTO legacy_records(source_id,source_id_raw,snapshot_cipher,fingerprint) VALUES(?,?,?,?)', (source['source_id'], item['source_id_raw'], self.vault.encrypt(raw), item['fingerprint'])).lastrowid
                            if not link or (link['ownership'] == 'following' and item['action'] != 'unchanged'):
                                normalized = self.normalize(raw, mappings)
                                order_id = self.apply(raw, normalized, record_id, link, applied_state_fingerprint(raw, source['version']))
                                self.conn.execute('UPDATE legacy_batch_items SET repair_order_id=? WHERE item_id=?', (order_id, item['item_id']))
                                for reference in normalized['references']:
                                    self.conn.execute('INSERT OR IGNORE INTO legacy_attachments(record_id,reference,reference_hash) VALUES(?,?,?)', (record_id, reference, digest(reference)))
                        self.conn.execute("UPDATE legacy_batch_items SET result='success' WHERE item_id=?", (item['item_id'],))
                except Exception as exc:
                    if not isinstance(exc, LegacyError):
                        logger.exception('Legacy import transaction failed: item %s', item['item_id'])
                    with self.write():
                        self.conn.execute("UPDATE legacy_batch_items SET result='failed',reason=? WHERE item_id=?", (str(exc) if isinstance(exc, LegacyError) else '本条导入事务失败，已回滚', item['item_id']))
            self.copy_images(source['source_id'], client)
            with self.write():
                unresolved = self.conn.execute("SELECT COUNT(*) FROM legacy_batch_items WHERE batch_id=? AND result IN ('failed','blocked','pending')", (batch_id,)).fetchone()[0]
                self.conn.execute('UPDATE legacy_batches SET status=?,completed_at=CURRENT_TIMESTAMP WHERE batch_id=?', ('partial' if unresolved else 'completed', batch_id))
                self.conn.execute("UPDATE legacy_sources SET operation_token='' WHERE source_id=?", (source['source_id'],))
        except Exception as exc:
            if not isinstance(exc, LegacyError):
                logger.exception('Legacy execute job failed: %s', batch_id)
            self.fail_job(batch_id, str(exc) if isinstance(exc, LegacyError) else '同步任务失败，请重试或重新预览')

    def apply(self, raw, normalized, record_id, link, applied):
        if link:
            machine_id, order_id = link['machine_id'], link['repair_order_id']
            others = self.conn.execute('SELECT COUNT(*) FROM repair_orders WHERE machine_id=? AND repair_order_id<>?', (machine_id, order_id)).fetchone()[0]
            if others:
                raise LegacyError('设备关联了其他工单，需要接管后维护或重新关联')
        else:
            machine_id = self.repo.create_machine({'machine_no': 'LG-' + uuid4().hex[:20], 'imei': None, 'serial': str(raw['串号'] or ''), 'model': str(raw['机型'] or '待补'), 'current_status': '到店', 'source_type': '维修', 'created_by': 'legacy-import'})
            order_id = self.repo.create_repair_order(machine_id, None, normalized['status'], str(raw['故障'] or ''), '', 'legacy-import')
            self.conn.execute('INSERT INTO legacy_links(record_id,repair_order_id,machine_id) VALUES(?,?,?)', (record_id, order_id, machine_id))
        self.conn.execute('UPDATE machines SET model=?,serial=?,updated_at=CURRENT_TIMESTAMP WHERE machine_id=?', (str(raw['机型'] or '待补'), str(raw['串号'] or ''), machine_id))
        self.conn.execute('''UPDATE repair_orders SET customer_name=?,source='老系统导入',fault_description=?,diagnosis=?,repair_solution=?,
            quoted_amount=?,assigned_to=?,status=?,workflow_status=?,payment_status='历史待确认',settlement_status='历史待确认',updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?''',
            (str(raw['顾客'] or ''), str(raw['故障'] or ''), str(raw['初诊'] or ''), str(raw['解决方案'] or ''), float(normalized['amounts']['报价'] or 0), normalized['assigned'], normalized['status'], '历史查询' if normalized['classification'] == 'history' else '待接管', order_id))
        if normalized['created']:
            self.conn.execute('UPDATE repair_orders SET created_at=? WHERE repair_order_id=?', (normalized['created'], order_id))
        self.conn.execute('''UPDATE legacy_links SET classification=?,applied_fingerprint=?,amounts_json=?,parts_json=?,original_engineer=?,original_payment=?,synced_at=CURRENT_TIMESTAMP WHERE record_id=?''',
            (normalized['classification'], applied, pack(normalized['amounts']), pack(normalized['parts']), str(raw['工程师'] or ''), str(raw['付款方式'] or ''), record_id))
        return order_id

    def associate(self, user, item_id, data):
        self.admin(user)
        with self.write():
            item = self.one('SELECT * FROM legacy_batch_items WHERE item_id=?', (item_id,))
            if not item or item['action'] in ('invalid', 'missing'):
                raise LegacyError('该来源记录不支持关联')
            batch = self.one('SELECT * FROM legacy_batches WHERE batch_id=?', (item['batch_id'],))
            if self.source(batch['source_id'])['operation_token']:
                raise LegacyError('来源任务进行中，请稍后关联')
            order = self.repo.get_repair_order(int(data['repair_order_id']))
            if not order or self.target_hash(order['repair_order_id']) != data.get('target_fingerprint'):
                raise LegacyError('目标不存在或已变化，请重新选择')
            if self.one('SELECT * FROM legacy_records WHERE source_id=? AND source_id_raw=?', (batch['source_id'], item['source_id_raw'])) or self.one('SELECT * FROM legacy_links WHERE repair_order_id=?', (order['repair_order_id'],)):
                raise LegacyError('来源或目标已经有关联')
            # Existing operational orders remain owned by the new system. This
            # prevents an association from overwriting finance or native items.
            rid = self.conn.execute('INSERT INTO legacy_records(source_id,source_id_raw,snapshot_cipher,fingerprint) VALUES(?,?,?,?)', (batch['source_id'], item['source_id_raw'], item['snapshot_cipher'], item['fingerprint'])).lastrowid
            self.conn.execute("INSERT INTO legacy_links(record_id,repair_order_id,machine_id,customer_id,ownership,classification,taken_by,taken_at) VALUES(?,?,?,?,'taken','active',?,CURRENT_TIMESTAMP)", (rid, order['repair_order_id'], order['machine_id'], order['customer_id'], user.username))
            self.audit(user, 'legacy:associate_taken', order['repair_order_id'])
        return {'ok': True, 'message': '已关联现有工单，新系统保持接管；请重新预览'}

    def candidates(self, user, q=''):
        self.admin(user)
        orders = self.rows("SELECT repair_order_id,order_no,customer_name,status FROM repair_orders WHERE archived_at='' AND NOT EXISTS(SELECT 1 FROM legacy_links l WHERE l.repair_order_id=repair_orders.repair_order_id) AND (order_no LIKE ? OR customer_name LIKE ?) ORDER BY repair_order_id DESC LIMIT 50", ('%' + q + '%', '%' + q + '%'))
        return [o | {'target_fingerprint': self.target_hash(o['repair_order_id'])} for o in orders]

    def detail(self, user, order_id, reveal=False):
        order = self.repo.get_repair_order(order_id)
        if not order or 'repair_order:read' not in self.repo.permissions_for_role(str(user.role)):
            raise PermissionError('没有工单读取权限')
        if user.role == Role.engineer and order['assigned_to'] != user.username:
            raise PermissionError('工程师仅查看本人指派工单')
        value = self.one('SELECT l.*,r.source_id,r.source_id_raw,r.snapshot_cipher,r.fingerprint,r.observed_at,r.missing FROM legacy_links l JOIN legacy_records r ON r.record_id=l.record_id WHERE l.repair_order_id=?', (order_id,))
        if not value:
            return None
        raw = self.vault.decrypt(value.pop('snapshot_cipher'))
        if not reveal:
            raw['锁屏密码'] = '••••••' if raw['锁屏密码'] else raw['锁屏密码']
        else:
            self.audit(user, 'legacy:reveal_lock_code', order_id)
            self.conn.commit()
        value['raw'] = raw
        value['amounts'] = json.loads(value.pop('amounts_json'))
        value['parts'] = json.loads(value.pop('parts_json'))
        value['attachments'] = self.rows('SELECT attachment_id,reference,status,error,photo_id FROM legacy_attachments WHERE record_id=?', (value['record_id'],))
        value['target_fingerprint'] = self.target_hash(order_id)
        return value

    def records(self, user, offset=0, limit=100, classification=''):
        if 'repair_order:read' not in self.repo.permissions_for_role(str(user.role)):
            raise PermissionError('没有维修读取权限')
        condition, params = "ro.archived_at=''", []
        if classification:
            condition += ' AND l.classification=?'
            params.append(classification)
        if user.role == Role.engineer:
            condition += ' AND ro.assigned_to=?'
            params.append(user.username)
        base = ' FROM legacy_links l JOIN legacy_records r ON r.record_id=l.record_id JOIN repair_orders ro ON ro.repair_order_id=l.repair_order_id JOIN machines m ON m.machine_id=l.machine_id WHERE ' + condition
        total = self.conn.execute('SELECT COUNT(*)' + base, params).fetchone()[0]
        items = self.rows('SELECT ro.repair_order_id,ro.order_no,ro.customer_name,ro.status,m.model,r.source_id_raw,r.missing,l.classification,l.ownership,l.synced_at,l.amounts_json' + base + ' ORDER BY ro.repair_order_id DESC LIMIT ? OFFSET ?', (*params, limit, offset))
        for item in items:
            item['amounts'] = json.loads(item.pop('amounts_json'))
        return {'items': items, 'total': total}

    def summary(self, user):
        if 'repair_order:read' not in self.repo.permissions_for_role(str(user.role)):
            raise PermissionError('没有维修读取权限')
        clause, params = '', ()
        if user.role == Role.engineer:
            clause, params = ' AND ro.assigned_to=?', (user.username,)
        rows = self.rows("SELECT l.classification,l.amounts_json FROM legacy_links l JOIN repair_orders ro ON ro.repair_order_id=l.repair_order_id WHERE ro.archived_at=''" + clause, params)
        counts = Counter(r['classification'] for r in rows)
        totals, unknown = {}, {}
        for field in ('报价', '成本', '利润', '人工费'):
            values = [json.loads(r['amounts_json']).get(field) for r in rows if r['classification'] == 'history']
            totals[field] = str(sum((Decimal(v) for v in values if v is not None), Decimal(0)))
            unknown[field] = sum(v is None for v in values)
        return {'counts': dict(counts), 'historical_amounts': totals, 'unknown_amount_counts': unknown, 'note': '历史账单口径，独立于实收、应收、库存和绩效'}

    def takeover(self, user, order_id, data):
        self.admin(user)
        statuses = {s.value for s in OrderStatus} - {'已结单', '已作废', '已入库', '已售出'}
        if data.get('status') not in statuses or data.get('confirmed') is not True:
            raise LegacyError('接管需要确认当前维修阶段及客户设备信息')
        due, paid = amount(data.get('initial_due')), amount(data.get('initial_paid'))
        if due is None or paid is None or Decimal(due) < 0 or Decimal(paid) < 0:
            raise LegacyError('接管需要明确填写历史已收金额和期初待收金额，允许填写零')
        with self.write():
            link = self.one('SELECT * FROM legacy_links WHERE repair_order_id=?', (order_id,))
            if not link or link['ownership'] != 'following':
                raise LegacyError('工单已接管或不是导入工单')
            if link['classification'] == 'history':
                raise LegacyError('历史完成单保留查询；需要继续维修时另开返修工单')
            record = self.one('SELECT * FROM legacy_records WHERE record_id=?', (link['record_id'],))
            if record['missing'] or self.source(record['source_id'])['operation_token']:
                raise LegacyError('来源缺失或同步任务进行中，请先核对')
            if data.get('target_fingerprint') != self.target_hash(order_id):
                raise LegacyError('工单已变化，请刷新后接管')
            raw = self.vault.decrypt(record['snapshot_cipher'])
            mapped = self.normalize(raw, json.loads(self.source(record['source_id'])['mappings_json']))
            if mapped['classification'] == 'history':
                raise LegacyError('来源按当前规则属于历史完成单，请重新预览并同步后查询')
            if mapped['classification'] == 'unknown':
                raise LegacyError('来源状态尚未确认，请先设置状态映射并重新同步')
            username = str(data.get('assigned_to', ''))
            if username and not self.one("SELECT * FROM users WHERE username=? AND enabled=1 AND employee_id IS NOT NULL AND role IN ('engineer','staff','admin')", (username,)):
                raise LegacyError('请选择有效工程师账号')
            if not username and (link['original_engineer'] or data['status'] in ('检测中', '已报价', '处理中')):
                raise LegacyError('当前阶段需要明确指派工程师')
            customer_id = data.get('customer_id')
            if customer_id and not self.repo.get_customer(int(customer_id)):
                raise LegacyError('所选客户不存在')
            self.conn.execute("UPDATE legacy_links SET ownership='taken',classification='active',taken_by=?,taken_at=CURRENT_TIMESTAMP,taken_stage=?,customer_id=?,initial_due=?,initial_paid=? WHERE repair_order_id=?", (user.username, data['status'], customer_id, due, paid, order_id))
            # Only the explicitly confirmed opening balance participates in the
            # new system's future billing. Historical paid money has no ledger row.
            self.conn.execute("UPDATE repair_orders SET status=?,workflow_status=?,assigned_to=?,customer_id=?,quoted_amount=?,payment_status='未收款',settlement_status='未结',updated_at=CURRENT_TIMESTAMP WHERE repair_order_id=?", (data['status'], data['status'], username, customer_id, float(due), order_id))
            self.conn.execute('UPDATE machines SET customer_id=?,assigned_to=?,current_status=? WHERE machine_id=?', (customer_id, username, {'已开单': '到店', '检测中': '检测中', '已报价': '已报价', '处理中': '维修中', '待交付': '待交付', '已交付': '已交付'}.get(data['status'], '到店'), link['machine_id']))
            self.repo.add_machine_event(link['machine_id'], 'repair', '接管老系统工单', '已确认期初余额及当前阶段', user.username, 'repair', order_id)
            self.audit(user, 'legacy:takeover', order_id)
        return {'ok': True}

    def copy_images(self, source_id, client=None):
        client = client or self.client(self.source(source_id))
        pending = self.rows("SELECT a.*,l.repair_order_id,l.ownership FROM legacy_attachments a JOIN legacy_records r ON r.record_id=a.record_id JOIN legacy_links l ON l.record_id=r.record_id WHERE r.source_id=? AND a.status<>'copied'", (source_id,))
        for attachment in pending:
            if attachment['ownership'] == 'taken':
                continue
            try:
                content, ext = client.image(attachment['reference'])
                content_hash = hashlib.sha256(content).hexdigest()
                folder = ROOT_DIR / 'uploads' / 'legacy'
                folder.mkdir(parents=True, exist_ok=True)
                file = folder / (content_hash + ext)
                if not file.exists():
                    temp = folder / (uuid4().hex + '.tmp')
                    temp.write_bytes(content)
                    temp.replace(file)
                with self.write():
                    # Takeover may have happened while the download was running.
                    link = self.one('SELECT * FROM legacy_links WHERE record_id=?', (attachment['record_id'],))
                    if link['ownership'] == 'taken':
                        continue
                    duplicate = self.one("SELECT photo_id FROM legacy_attachments WHERE record_id=? AND content_hash=? AND status='copied'", (attachment['record_id'], content_hash))
                    photo_id = duplicate['photo_id'] if duplicate else self.repo.add_repair_order_photo(link['repair_order_id'], 'pre', file.name, '/uploads/legacy/' + file.name, 'legacy-import')
                    self.conn.execute("UPDATE legacy_attachments SET status='copied',content_hash=?,photo_id=?,error='' WHERE attachment_id=?", (content_hash, photo_id, attachment['attachment_id']))
            except Exception as exc:
                with self.write():
                    self.conn.execute("UPDATE legacy_attachments SET status='failed',error=? WHERE attachment_id=?", (str(exc) if isinstance(exc, LegacyError) else '图片复制失败，请重试', attachment['attachment_id']))


def recover_jobs(conn):
    conn.execute("UPDATE legacy_fetch_jobs SET status='interrupted',error='服务重启中断暂存拉取，已收到页面保留，请重新增量拉取' WHERE status IN ('queued','reading')")
    conn.execute("UPDATE legacy_batches SET status='interrupted',error='服务重启中断了任务；可重试已生成预览的批次，其余重新读取' WHERE status IN ('queued','reading','queued_execute','executing')")
    conn.execute("UPDATE legacy_sources SET operation_token=''")
    conn.commit()
