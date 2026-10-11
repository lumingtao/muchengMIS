from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from backend.db import connect, migrate
from backend.legacy_client import FIELDS, LegacyClient, LegacyError
from backend.legacy_import import LegacyImportService, recover_jobs
from backend.models import Role, User, PaymentInput, PaymentDirection
from backend.service import MisService

ADMIN = User(username='admin', role=Role.admin)


def bill(identity='1', **values):
    raw = dict.fromkeys(FIELDS, '')
    raw.update({'ID': identity, '机型': 'iPhone 13', '时间': '2022-03-17 00:00:00', '串号': '1', '顾客': '散客', '备注': '维修中', '工程师': '曹新', '报价': '200', '成本': '0', '锁屏密码': 'fixture-code'})
    raw.update(values)
    return raw


class FixtureClient(LegacyClient):
    def __init__(self, rows):
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE "维修账单" (' + ','.join('"'+f+'" TEXT' for f in FIELDS) + ')')
        self.db.executemany('INSERT INTO "维修账单" VALUES (' + ','.join('?' for _ in FIELDS) + ')', [[r[f] for f in FIELDS] for r in rows])
        self.calls = []
        self.image_calls = 0
        self.fail_image = False

    def query(self, sql):
        self.calls.append(sql)
        return [dict(r) for r in self.db.execute(sql).fetchmany(500)]

    def image(self, reference):
        self.image_calls += 1
        if self.fail_image:
            raise LegacyError('fixture 图片失败')
        return b'\x89PNG\r\n\x1a\nfixture', '.png'

    def change(self, identity, field, value):
        self.db.execute(f'UPDATE "维修账单" SET "{field}"=? WHERE "ID"=?', (value, identity))


@pytest.fixture
def setup(tmp_path):
    conn = connect(tmp_path / 'target.sqlite3')
    migrate(conn)
    client = FixtureClient([bill()])
    svc = LegacyImportService(conn, client_factory=lambda *args: client)
    svc.save_source(ADMIN, {'base_url': 'https://fixture.example', 'username': 'fixture', 'password': 'fixture-password'})
    yield svc, client
    conn.close()


def preview(svc, filters=None):
    pull = svc.new_fetch(ADMIN, 'full')
    svc.fetch_cache(pull)
    assert svc.cache_status(ADMIN)['job']['status'] == 'completed', svc.cache_status(ADMIN)
    batch_id = svc.new_batch(ADMIN, filters or {})
    svc.preview(batch_id)
    assert svc.batch(ADMIN, batch_id)['status'] == 'preview'
    return batch_id


def execute(svc, batch_id):
    svc.queue_execution(ADMIN, batch_id, item_ids=[row['item_id'] for row in svc.items(ADMIN, batch_id)])
    svc.execute(batch_id)
    return svc.batch(ADMIN, batch_id)


def test_complete_fields_and_repeat_import(setup):
    svc, client = setup
    first = execute(svc, preview(svc))
    assert first['status'] == 'completed', svc.items(ADMIN, first['batch_id'])
    assert Path(first['backup_path']).exists()
    link = svc.one('SELECT * FROM legacy_links')
    record = svc.one('SELECT * FROM legacy_records')
    raw = svc.vault.decrypt(record['snapshot_cipher'])
    assert raw == bill()
    assert len(raw) == 23
    assert 'fixture-code' not in record['snapshot_cipher']
    assert json.loads(link['amounts_json'])['成本'] == '0'
    assert json.loads(link['amounts_json'])['利润'] is None
    before = svc.target_hash(link['repair_order_id'])
    again = preview(svc)
    assert svc.items(ADMIN, again)[0]['action'] == 'unchanged'
    execute(svc, again)
    assert svc.target_hash(link['repair_order_id']) == before
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 1
    assert svc.conn.execute('SELECT COUNT(*) FROM machines').fetchone()[0] == 1
    for table in ('payments', 'repair_materials', 'repair_items', 'stock_movements', 'repair_material_reservations'):
        assert svc.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    assert MisService(svc.conn).repair_workbench(ADMIN)['orders'] == []


def test_pagination_and_unstable_scan():
    client = FixtureClient([bill(str(i)) for i in range(1007)])
    result = client.scan()
    assert len(result) == 1007
    assert len({r['ID'] for r in result}) == 1007
    assert len([q for q in client.calls if 'LIMIT 500' in q]) == 8
    original = client._scan
    calls = 0
    def changing():
        nonlocal calls
        calls += 1
        if calls == 2:
            client.change('1', '报价', '300')
        return original()
    client._scan = changing
    with pytest.raises(LegacyError, match='内容发生变化'):
        client.scan()


def test_local_staging_incremental_and_offline_preview(setup):
    svc, _ = setup
    rows = [bill(str(i), 更新时间='2022-01-01 00:00:00') for i in range(1, 1201)]
    rows[-1]['更新时间'] = '2026-10-01 00:00:00'
    client = FixtureClient(rows)
    svc.client_factory = lambda *args: client
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    assert svc.cache_status(ADMIN)['total'] == 1200
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 0
    client.calls.clear()
    svc.client_factory = lambda *args: (_ for _ in ()).throw(AssertionError('local preview must not connect'))
    batch = svc.new_batch(ADMIN, {'ids': ['1199']}); svc.preview(batch)
    assert svc.batch(ADMIN, batch)['status'] == 'preview'
    assert client.calls == []
    assert svc.items(ADMIN, batch)[0]['source_id_raw'] == '1199'
    svc.client_factory = lambda *args: client
    client.change('1100', '报价', '350'); client.change('1100', '更新时间', '2026-10-02 00:00:00')
    raw = bill('1201', 更新时间='2026-10-02 00:00:00')
    client.db.execute('INSERT INTO "维修账单" VALUES (' + ','.join('?' for _ in FIELDS) + ')', [raw[f] for f in FIELDS])
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    result = svc.cache_status(ADMIN)['job']['result']
    assert result['mode'] == 'incremental'
    assert result['new'] == 1 and result['changed'] == 1
    assert result['received'] < 510
    assert not any('COUNT(*) AS n, COALESCE' in q for q in client.calls)
    # Old rows with unchanged timestamps are found by the next rotating page.
    client.change('800', '报价', '450')
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    stored = svc.one('SELECT snapshot_cipher FROM legacy_cache WHERE source_id_raw=?', ('800',))
    assert svc.vault.decrypt(stored['snapshot_cipher'])['报价'] == '450'
    with pytest.raises(LegacyError, match='暂存数据已变化'):
        svc.queue_execution(ADMIN, batch, item_ids=[svc.items(ADMIN, batch)[0]['item_id']])


def test_cache_exclusion_notes_and_selected_sync(setup):
    svc, _ = setup
    client = FixtureClient([bill('1'), bill('2'), bill('3')])
    svc.client_factory = lambda *args: client
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    svc.manage_cache(ADMIN, 1, {'excluded': True, 'management_note': 'keep in staging'})
    assert svc.cache_records(ADMIN, {})['total'] == 2
    assert svc.cache_records(ADMIN, {}, include_excluded=True)['total'] == 3
    batch = svc.new_batch(ADMIN, {}); svc.preview(batch)
    assert {i['source_id_raw'] for i in svc.items(ADMIN, batch)} == {'2', '3'}
    with pytest.raises(LegacyError, match='明确勾选'):
        svc.queue_execution(ADMIN, batch)
    item = svc.items(ADMIN, batch)[0]
    client.calls.clear()
    svc.queue_execution(ADMIN, batch, item_ids=[item['item_id']]); svc.execute(batch)
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 1
    assert not any('COUNT(*) AS n' in q for q in client.calls)
    assert svc.rows('SELECT source_id_raw FROM legacy_records') == [{'source_id_raw': '2'}]
    assert svc.one('SELECT management_note FROM legacy_cache WHERE source_rowid=1')['management_note'] == 'keep in staging'
    client.change('3', '报价', '500')
    client.calls.clear()
    svc.refresh_cache_row(ADMIN, 3)
    refreshed = svc.cache_records(ADMIN, {}, q='3')['items'][0]
    assert refreshed['raw']['报价'] == '500'
    assert len(client.calls) == 1


def test_incremental_failure_keeps_cursor_and_restart_state(setup):
    svc, client = setup
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    original = client.query
    def failed(sql):
        if 'WHERE rowid>' in sql:
            raise LegacyError('fixture interrupted')
        return original(sql)
    client.query = failed
    job = svc.new_fetch(ADMIN); svc.fetch_cache(job)
    state = svc.cache_status(ADMIN)
    assert state['job']['status'] == 'failed' and state['high_rowid'] == 1
    client.query = original
    pending = svc.new_fetch(ADMIN)
    recover_jobs(svc.conn)
    assert svc.cache_status(ADMIN)['job']['status'] == 'interrupted'
    assert svc.cache_status(ADMIN)['high_rowid'] == 1
    assert svc.one('SELECT COUNT(*) AS n FROM legacy_cache')['n'] == 1


def test_update_and_stale_source(setup):
    svc, client = setup
    execute(svc, preview(svc))
    client.change('1', '报价', '300')
    batch = preview(svc)
    assert svc.items(ADMIN, batch)[0]['action'] == 'update'
    client.change('1', '报价', '400')
    assert execute(svc, batch)['status'] == 'partial'
    assert svc.one('SELECT quoted_amount FROM repair_orders')['quoted_amount'] == 200
    changed = preview(svc)
    assert execute(svc, changed)['status'] == 'completed'
    assert svc.one('SELECT quoted_amount FROM repair_orders')['quoted_amount'] == 400
    saved = svc.item_detail(ADMIN, svc.items(ADMIN, changed)[0]['item_id'])
    assert saved['previous']['报价'] == '200'
    assert saved['raw']['报价'] == '400'


def test_takeover_freezes_and_guards_writes(setup):
    svc, client = setup
    execute(svc, preview(svc))
    order_id = svc.one('SELECT * FROM legacy_links')['repair_order_id']
    for sql in ["UPDATE repair_orders SET quoted_amount=9", "UPDATE machines SET model='changed'", "INSERT INTO repair_items(repair_order_id,item_name) VALUES(1,'fixture')"]:
        with pytest.raises(sqlite3.IntegrityError, match='先接管'):
            svc.conn.execute(sql)
        svc.conn.rollback()
    data = {'status': '已交付', 'confirmed': True, 'assigned_to': 'engineer', 'initial_due': '80', 'initial_paid': '120', 'target_fingerprint': svc.target_hash(order_id)}
    with pytest.raises(PermissionError):
        svc.takeover(User(username='frontdesk', role=Role.frontdesk), order_id, data)
    svc.takeover(ADMIN, order_id, data)
    before = svc.target_hash(order_id)
    client.change('1', '报价', '900')
    client.change('1', '机型', 'changed in old')
    batch = preview(svc)
    assert svc.items(ADMIN, batch)[0]['action'] == 'taken_changed'
    execute(svc, batch)
    assert svc.target_hash(order_id) == before
    assert svc.one('SELECT quoted_amount FROM repair_orders')['quoted_amount'] == 80
    assert svc.conn.execute('SELECT COUNT(*) FROM payments').fetchone()[0] == 0
    svc.conn.execute("UPDATE repair_orders SET remark='new-system-note'")
    svc.conn.commit()


def test_confirmed_delivery_collects_only_opening_balance(setup):
    svc, _ = setup
    execute(svc, preview(svc))
    order_id = svc.one('SELECT * FROM legacy_links')['repair_order_id']
    detail = svc.detail(ADMIN, order_id)
    assert detail['target_fingerprint'] == svc.target_hash(order_id)
    svc.takeover(ADMIN, order_id, {'status': '已交付', 'confirmed': True,
        'assigned_to': 'engineer', 'initial_due': '80', 'initial_paid': '120',
        'target_fingerprint': detail['target_fingerprint']})
    assert not svc.one('SELECT engineer_closed_at FROM repair_orders')['engineer_closed_at']
    MisService(svc.conn).create_payment(ADMIN, PaymentInput(source_type='repair', source_id=order_id,
        direction=PaymentDirection.income, amount=80, method='现金'))
    assert svc.one('SELECT SUM(amount) AS total FROM payments')['total'] == 80


def test_concurrent_numbering_and_five_digit_suffix(setup):
    from concurrent.futures import ThreadPoolExecutor
    from backend.repository import Repository
    svc, _ = setup
    execute(svc, preview(svc))
    machine_id = svc.one('SELECT * FROM legacy_links')['machine_id']
    database_path = svc.database_path
    def create_many():
        connection = connect(database_path)
        try:
            repo = Repository(connection)
            for _ in range(12):
                repo.create_repair_order(machine_id, None, '已开单', 'fixture', '', 'admin')
                connection.commit()
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: create_many(), range(2)))
    numbers = [r['order_no'] for r in svc.rows('SELECT order_no FROM repair_orders')]
    assert len(numbers) == len(set(numbers)) == 25
    prefix = numbers[0].rsplit('-', 1)[0]
    svc.conn.execute('UPDATE repair_orders SET order_no=? WHERE repair_order_id=(SELECT MAX(repair_order_id) FROM repair_orders)', (prefix + '-10000',))
    svc.conn.commit()
    assert svc.repo.next_order_no('repair_orders', 'WX') == prefix + '-10001'


def test_bad_identity_and_amounts(setup):
    svc, _ = setup
    client = FixtureClient([bill(''), bill('dup'), bill('dup'), bill('money', 报价='bad'), bill('unknown', 备注='unmapped')])
    svc.client_factory = lambda *args: client
    batch = preview(svc)
    actions = [r['action'] for r in svc.items(ADMIN, batch)]
    assert actions.count('invalid') == 3
    assert actions.count('review') == 2
    assert execute(svc, batch)['status'] == 'partial'
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 0


def test_deletion_only_full_scan_and_restart(setup):
    svc, client = setup
    execute(svc, preview(svc))
    client.db.execute('DELETE FROM "维修账单"')
    filtered = preview(svc, {'ids': ['1']})
    assert svc.items(ADMIN, filtered) == []
    complete = preview(svc)
    assert svc.items(ADMIN, complete)[0]['action'] == 'missing'
    execute(svc, complete)
    assert svc.one('SELECT missing FROM legacy_records')['missing'] == 1
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 1
    pending = svc.new_batch(ADMIN, {})
    with pytest.raises(LegacyError, match='任务'):
        svc.new_batch(ADMIN, {})
    recover_jobs(svc.conn)
    assert svc.batch(ADMIN, pending)['status'] == 'interrupted'
    assert svc.source()['operation_token'] == ''


def test_mapping_invalidates_preview_and_secret_redaction(setup):
    svc, _ = setup
    batch = preview(svc)
    item = svc.items(ADMIN, batch)[0]
    assert svc.item_detail(ADMIN, item['item_id'])['raw']['锁屏密码'] == '••••••'
    assert 'password' not in svc.public_source(ADMIN)
    svc.mappings(ADMIN, {'engineers': {'曹新': 'engineer'}})
    with pytest.raises(LegacyError, match='映射'):
        svc.queue_execution(ADMIN, batch, item_ids=[item['item_id']])


def test_history_and_independent_devices(setup):
    svc, _ = setup
    client = FixtureClient([bill('1', 备注='维修完成', 付款方式='已结账/已取机'), bill('2', 备注='维修完成', 付款方式='已结账/已取机')])
    svc.client_factory = lambda *args: client
    execute(svc, preview(svc))
    assert svc.conn.execute('SELECT COUNT(*) FROM machines').fetchone()[0] == 2
    assert svc.records(ADMIN, classification='history')['total'] == 2
    assert MisService(svc.conn).repair_workbench(ADMIN)['orders'] == []
    assert svc.repo.unsettled_repair_orders_for_customer(1) == []


def test_images_retry_and_duplicate(tmp_path, monkeypatch):
    import backend.legacy_import as module
    monkeypatch.setattr(module, 'ROOT_DIR', tmp_path)
    conn = connect(tmp_path / 'images.sqlite3'); migrate(conn)
    client = FixtureClient([bill(图片='["/a.png","/b.png"]')])
    client.fail_image = True
    svc = LegacyImportService(conn, client_factory=lambda *args: client)
    svc.save_source(ADMIN, {'base_url': 'https://fixture.example', 'username': 'fixture', 'password': 'fixture'})
    assert execute(svc, preview(svc))['status'] == 'completed'
    assert {r['status'] for r in svc.rows('SELECT * FROM legacy_attachments')} == {'failed'}
    client.fail_image = False
    svc.copy_images('wuxi-legacy', client)
    assert conn.execute('SELECT COUNT(*) FROM repair_order_photos').fetchone()[0] == 1
    assert {r['status'] for r in svc.rows('SELECT * FROM legacy_attachments')} == {'copied'}
    before = client.image_calls
    svc.copy_images('wuxi-legacy', client)
    assert client.image_calls == before
    conn.close()


def test_target_change_is_detected(setup):
    svc, client = setup
    execute(svc, preview(svc))
    client.change('1', '报价', '250')
    batch = preview(svc)
    with svc.write():
        svc.conn.execute("UPDATE repair_orders SET remark='changed-after-preview'")
    assert execute(svc, batch)['status'] == 'partial'
    assert '目标工单已变化' in svc.items(ADMIN, batch)[0]['reason']


def test_service_guards_before_side_effects_and_restart_migration(setup):
    from backend.models import RepairItemInput, MachineUpdateInput
    from backend.service import BusinessError
    svc, _ = setup
    execute(svc, preview(svc))
    business = MisService(svc.conn)
    with pytest.raises(BusinessError, match='先接管'):
        business.add_repair_item(ADMIN, 1, RepairItemInput(item_name='should-not-create-sku', cost_amount=5))
    with pytest.raises(BusinessError, match='先接管'):
        business.update_machine(ADMIN, 1, MachineUpdateInput(model='changed', current_status='到店'))
    assert svc.conn.execute("SELECT COUNT(*) FROM repair_skus WHERE solution_name='should-not-create-sku'").fetchone()[0] == 0
    before = svc.target_hash(1)
    migrate(svc.conn)
    assert svc.target_hash(1) == before


def test_associate_existing_preserves_native_order(setup):
    svc, _ = setup
    batch = preview(svc)
    with svc.write():
        machine = svc.repo.create_machine({'machine_no': 'existing', 'model': 'existing', 'current_status': '维修中'})
        order = svc.repo.create_repair_order(machine, None, '处理中', 'native-fault', 'native-note', 'admin')
    original = svc.one('SELECT * FROM repair_orders WHERE repair_order_id=?', (order,))
    item = svc.items(ADMIN, batch)[0]
    candidate = next(c for c in svc.candidates(ADMIN) if c['repair_order_id'] == order)
    svc.associate(ADMIN, item['item_id'], candidate)
    assert svc.one('SELECT * FROM repair_orders WHERE repair_order_id=?', (order,)) == original
    assert svc.one('SELECT ownership FROM legacy_links')['ownership'] == 'taken'
    execute(svc, batch)
    assert '对应关系已变化' in svc.items(ADMIN, batch)[0]['reason']
    assert execute(svc, preview(svc))['status'] == 'completed'
    assert svc.conn.execute('SELECT COUNT(*) FROM repair_orders').fetchone()[0] == 1


def test_interrupted_read_cannot_execute(setup):
    svc, _ = setup
    batch = svc.new_batch(ADMIN, {})
    recover_jobs(svc.conn)
    with pytest.raises(LegacyError, match='未完成'):
        svc.queue_execution(ADMIN, batch)


def test_api_authorization_background_work_and_redaction(setup, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import app, get_service
    svc, remote = setup
    monkeypatch.setattr(LegacyImportService, 'client', lambda self, source: remote)
    def dependency():
        conn = connect(svc.database_path)
        try:
            yield MisService(conn)
        finally:
            conn.close()
    app.dependency_overrides[get_service] = dependency
    try:
        client = TestClient(app)
        assert client.get('/api/legacy-import/source').status_code == 401
        client.post('/api/login', json={'username': 'frontdesk', 'password': 'frontdesk'})
        assert client.get('/api/legacy-import/source').status_code == 403
        client.post('/api/login', json={'username': 'admin', 'password': 'admin'})
        config = client.get('/api/legacy-import/source')
        assert config.status_code == 200
        assert 'fixture-password' not in config.text
        assert client.post('/api/legacy-import/cache/fetch', json={}).status_code == 200
        assert client.get('/api/legacy-import/cache/status').json()['total'] == 1
        assert client.get('/api/legacy-import/records').json()['total'] == 0
        batch_id = client.post('/api/legacy-import/preview', json={}).json()['batch_id']
        assert client.get(f'/api/legacy-import/batches/{batch_id}').json()['status'] == 'preview'
        item_id = client.get(f'/api/legacy-import/batches/{batch_id}/items').json()[0]['item_id']
        assert 'fixture-code' not in client.get(f'/api/legacy-import/items/{item_id}').text
        assert client.post(f'/api/legacy-import/batches/{batch_id}/execute', json={'item_ids': [item_id]}).status_code == 200
        assert client.get('/api/legacy-import/records').json()['total'] == 1, client.get(f'/api/legacy-import/batches/{batch_id}').json()
        assert client.get('/api/repair-workbench').json()['orders'] == []
        response = client.post('/api/repair-orders/1/items', json={'item_name': 'bad', 'cost_amount': 2})
        assert response.status_code in (400, 409), response.text
        detail = client.get('/api/legacy-import/orders/1').json()
        assert detail['raw']['锁屏密码'] == '••••••'
        assert client.post('/api/legacy-import/orders/1/lock-code').json()['raw']['锁屏密码'] == 'fixture-code'
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('remark,classification,status', [
    ('待维修', 'active', '已开单'),
    ('待取机', 'active', '待交付'),
    ('待结账', 'active', '已交付'),
    ('维修完成', 'history', '已结单'),
])
def test_verified_miniapp_flow(setup, remark, classification, status):
    svc, client = setup
    client.change('1', '备注', remark)
    client.change('1', '付款方式', '待维修')
    batch = preview(svc)
    assert svc.items(ADMIN, batch)[0]['action'] == 'new'
    assert execute(svc, batch)['status'] == 'completed'
    link = svc.one('SELECT * FROM legacy_links')
    order = svc.repo.get_repair_order(link['repair_order_id'])
    assert link['classification'] == classification
    assert order['status'] == status
    assert link['original_payment'] == '待维修'
    for table in ('payments', 'stock_movements'):
        assert svc.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    assert svc.items(ADMIN, preview(svc))[0]['action'] == 'unchanged'


def test_corrected_rule_updates_old_fingerprint_and_rejects_old_preview(setup):
    from backend.legacy_client import digest
    svc, client = setup
    client.change('1', '备注', '维修完成')
    client.change('1', '付款方式', '待维修')
    execute(svc, preview(svc))
    record = svc.one('SELECT * FROM legacy_records')
    old_fingerprint = digest([record['fingerprint'], svc.source()['version']])
    svc.conn.execute('UPDATE legacy_links SET applied_fingerprint=?', (old_fingerprint,))
    svc.conn.commit()
    batch = preview(svc)
    assert svc.items(ADMIN, batch)[0]['action'] == 'update'
    profile = svc.batch(ADMIN, batch)['profile']
    profile.pop('state_rule_version')
    svc.conn.execute('UPDATE legacy_batches SET profile_json=? WHERE batch_id=?', (json.dumps(profile), batch))
    svc.conn.commit()
    with pytest.raises(LegacyError, match='状态识别规则已更新'):
        svc.queue_execution(ADMIN, batch, item_ids=[svc.items(ADMIN, batch)[0]['item_id']])


def test_verified_rule_preserves_other_combinations_and_manual_override(setup):
    svc, _ = setup
    raw = bill(备注='维修完成', 付款方式='同行挂帐')
    result = svc.normalize(raw, {})
    assert (result['classification'], result['status']) == ('active', '待交付')
    for remark in ('无成本', '已退机'):
        assert svc.normalize(bill(备注=remark, 付款方式='待维修'), {})['classification'] == 'unknown'
    override = {'states': {'维修完成|待维修': {'classification': 'unknown', 'status': '已开单'}}}
    result = svc.normalize(bill(备注='维修完成', 付款方式='待维修'), override)
    assert (result['classification'], result['status']) == ('unknown', '已开单')
