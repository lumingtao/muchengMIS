from __future__ import annotations

import hashlib
import http.cookiejar
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

FIELDS = ['ID', '机型', '时间', '串号', '顾客', '备注', '解决方案', '工程师', '配件1', '付款方式', '图片', '故障', '配件来源', '配件2', '配件3', '报价', '成本', '利润', '电话', '人工费', '初诊', '更新时间', '锁屏密码']


class LegacyError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LegacyError('API 地址需要为 HTTPS 地址，且不含账号、查询或片段')
    return value.rstrip('/').removesuffix('/api')


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(req.full_url).netloc != urlsplit(newurl).netloc or urlsplit(newurl).scheme != 'https':
            raise LegacyError('来源请求跳转到了其他站点')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LegacyClient:
    def __init__(self, base_url, username, password, store_key='wuxi'):
        self.base = validate_url(base_url)
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()), SameOriginRedirect())
        self.headers = {'Content-Type': 'application/json', 'X-Store-Key': store_key}
        login = self.request('/api/login', {'username': username, 'password': password, 'storeKey': store_key})
        if isinstance(login, dict) and login.get('storeKey') and login['storeKey'] != store_key:
            raise LegacyError('登录返回的门店与配置不一致，请核对来源')

    def request(self, path, payload=None):
        try:
            request = Request(self.base + path, headers=self.headers, data=None if payload is None else json.dumps(payload).encode())
            with self.opener.open(request, timeout=30) as response:
                body = json.loads(response.read(32 * 1024 * 1024).decode('utf-8'))
            if isinstance(body, dict) and body.get('success') is False:
                raise LegacyError('老系统请求失败，请检查权限或查询接口')
            return body.get('data', body) if isinstance(body, dict) else body
        except HTTPError as exc:
            raise LegacyError(f'老系统返回 HTTP {exc.code}，请检查登录和读取权限') from None
        except (URLError, OSError, json.JSONDecodeError):
            raise LegacyError('老系统连接或响应异常，请重试') from None

    def query(self, sql):
        data = self.request('/api/admin/sql/run', {'sql': sql, 'writeEnabled': False})
        if not isinstance(data, dict) or not isinstance(data.get('rows'), list):
            raise LegacyError('老系统 SQL 返回格式异常')
        return data['rows']

    def _scan(self):
        boundary = self.query('SELECT COUNT(*) AS n, COALESCE(MAX(rowid),0) AS boundary FROM "维修账单"')[0]
        last, result = 0, []
        columns = ','.join('"' + field + '"' for field in FIELDS)
        while True:
            page = self.query(f'SELECT rowid AS "__rowid",{columns} FROM "维修账单" WHERE rowid>{int(last)} AND rowid<={int(boundary["boundary"])} ORDER BY rowid LIMIT 500')
            if not page:
                break
            for row in page:
                if '__rowid' not in row or any(f not in row for f in FIELDS):
                    raise LegacyError('老系统字段结构发生变化，请重新核对')
                if int(row['__rowid']) <= last:
                    raise LegacyError('来源分页顺序异常')
                last = int(row['__rowid'])
                result.append(row)
            if getattr(self, 'page_receiver', None):
                self.page_receiver(page)
            if getattr(self, 'progress', None):
                self.progress(len(result), int(boundary['n']))
        after = self.query('SELECT COUNT(*) AS n, COALESCE(MAX(rowid),0) AS boundary FROM "维修账单"')[0]
        if boundary != after or len(result) != int(boundary['n']):
            raise LegacyError(f'扫描期间老系统记录发生变化（开始 {boundary["n"]} 条，结束 {after["n"]} 条，读取 {len(result)} 条），请刷新预览')
        return result

    def scan(self):
        first = self._scan()
        # Double-read also detects same-count deletes/reinserts and edits to rows
        # already scanned. Timestamp fields in the legacy database are unreliable.
        if digest(first) != digest(self._scan()):
            raise LegacyError('扫描期间老系统内容发生变化，请刷新预览')
        return first

    def image(self, reference):
        url = urljoin(self.base + '/', reference)
        if urlsplit(url).netloc != urlsplit(self.base).netloc or urlsplit(url).scheme != 'https':
            raise LegacyError('图片引用不是来源站点地址，需要人工核对')
        try:
            with self.opener.open(Request(url, headers={'X-Store-Key': self.headers['X-Store-Key']}), timeout=30) as response:
                content = response.read(10 * 1024 * 1024 + 1)
            if len(content) > 10 * 1024 * 1024:
                raise LegacyError('图片超过 10MB')
            if content.startswith(b'\x89PNG\r\n\x1a\n'):
                ext = '.png'
            elif content.startswith(b'\xff\xd8\xff'):
                ext = '.jpg'
            elif content.startswith((b'GIF87a', b'GIF89a')):
                ext = '.gif'
            elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
                ext = '.webp'
            else:
                raise LegacyError('响应不是受支持的图片文件')
            return content, ext
        except (HTTPError, URLError, OSError):
            raise LegacyError('图片读取失败，请检查引用和登录状态') from None
