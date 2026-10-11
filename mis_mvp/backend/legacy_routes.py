from __future__ import annotations

import sqlite3
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from .db import connect
from .legacy_import import LegacyImportService
from .legacy_client import LegacyError
from .models import User


def legacy_router(current_user, get_service):
    router = APIRouter(prefix='/api/legacy-import', tags=['legacy-import'])

    def service(business=Depends(get_service)):
        return LegacyImportService(business.conn)

    def call(fn):
        try:
            return fn()
        except LegacyError as exc:
            raise HTTPException(400, str(exc)) from None
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, '参数格式异常') from None
        except sqlite3.IntegrityError:
            raise HTTPException(409, '来源或目标已有对应关系，请刷新后重试') from None

    def job(database_path, operation, argument):
        conn = connect(database_path)
        try:
            instance = LegacyImportService(conn)
            if operation == 'images':
                try:
                    instance.copy_images(argument)
                finally:
                    conn.rollback()
                    conn.execute("UPDATE legacy_sources SET operation_token='' WHERE source_id=?", (argument,))
                    conn.commit()
            else:
                getattr(instance, operation)(argument)
        finally:
            conn.close()

    @router.get('/source')
    def source(user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.public_source(user))

    @router.put('/source')
    def configure(data: dict, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.save_source(user, data))

    @router.post('/source/test')
    def test(user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.test_connection(user))

    @router.put('/mappings')
    def mappings(data: dict, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.mappings(user, data))

    @router.get('/cache/status')
    def cache_status(user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.cache_status(user))

    @router.post('/cache/fetch')
    def cache_fetch(data: dict, tasks: BackgroundTasks, user: User = Depends(current_user), svc=Depends(service)):
        job_id = call(lambda: svc.new_fetch(user, data.get('mode', 'incremental')))
        tasks.add_task(job, svc.database_path, 'fetch_cache', job_id)
        return {'job_id': job_id}

    @router.get('/cache/records')
    def cache_records(q: str = '', date_from: str = '', date_to: str = '', ids: str = '', include_excluded: bool = False, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500), user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.cache_records(user, {'date_from': date_from, 'date_to': date_to, 'ids': ids.split(',') if ids else []}, q, offset, limit, include_excluded))

    @router.patch('/cache/records/{rowid}')
    def cache_manage(rowid: int, data: dict, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.manage_cache(user, rowid, data))

    @router.post('/cache/records/{rowid}/refresh')
    def cache_refresh(rowid: int, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.refresh_cache_row(user, rowid))

    @router.post('/preview')
    def preview(data: dict, tasks: BackgroundTasks, user: User = Depends(current_user), svc=Depends(service)):
        batch_id = call(lambda: svc.new_batch(user, data))
        tasks.add_task(job, svc.database_path, 'preview', batch_id)
        return {'batch_id': batch_id}

    @router.get('/batches')
    def batches(user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.batches(user))

    @router.get('/batches/{batch_id}')
    def batch(batch_id: str, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.batch(user, batch_id))

    @router.get('/batches/{batch_id}/items')
    def items(batch_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.items(user, batch_id, offset, limit))

    @router.post('/batches/{batch_id}/execute')
    def execute(batch_id: str, data: dict, tasks: BackgroundTasks, user: User = Depends(current_user), svc=Depends(service)):
        call(lambda: svc.queue_execution(user, batch_id, item_ids=data.get('item_ids')))
        tasks.add_task(job, svc.database_path, 'execute', batch_id)
        return {'batch_id': batch_id, 'status': 'queued_execute'}

    @router.post('/batches/{batch_id}/retry')
    def retry(batch_id: str, tasks: BackgroundTasks, user: User = Depends(current_user), svc=Depends(service)):
        call(lambda: svc.queue_execution(user, batch_id, retry=True))
        tasks.add_task(job, svc.database_path, 'execute', batch_id)
        return {'batch_id': batch_id, 'status': 'queued_execute'}

    @router.get('/items/{item_id}')
    def item(item_id: int, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.item_detail(user, item_id))

    @router.post('/items/{item_id}/associate')
    def associate(item_id: int, data: dict, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.associate(user, item_id, data))

    @router.get('/candidates')
    def candidates(q: str = '', user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.candidates(user, q))

    @router.get('/records')
    def records(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), classification: str = '', user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.records(user, offset, limit, classification))

    @router.get('/summary')
    def summary(user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.summary(user))

    @router.get('/orders/{order_id}')
    def order(order_id: int, user: User = Depends(current_user), svc=Depends(service)):
        value = call(lambda: svc.detail(user, order_id))
        if value:
            value['target_fingerprint'] = svc.target_hash(order_id)
        return value

    @router.post('/orders/{order_id}/lock-code')
    def lock_code(order_id: int, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.detail(user, order_id, reveal=True))

    @router.post('/orders/{order_id}/takeover')
    def takeover(order_id: int, data: dict, user: User = Depends(current_user), svc=Depends(service)):
        return call(lambda: svc.takeover(user, order_id, data))

    @router.post('/attachments/retry')
    def images(tasks: BackgroundTasks, user: User = Depends(current_user), svc=Depends(service)):
        def queue():
            svc.admin(user)
            with svc.write():
                source = svc.source()
                if source['operation_token']:
                    raise LegacyError('来源任务进行中，请稍后重试')
                svc.conn.execute("UPDATE legacy_sources SET operation_token='images' WHERE source_id=?", (source['source_id'],))
                svc.audit(user, 'legacy:retry_images', source['source_id'])
            return source['source_id']
        source_id = call(queue)
        tasks.add_task(job, svc.database_path, 'images', source_id)
        return {'status': 'queued'}

    return router
