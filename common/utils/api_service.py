# utils/api_service.py
import logging
from common.utils.http_client import HttpClient
from common.utils.read_yaml import read_case

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
class ApiService:

    def __init__(self, test_file_name,base_url):
        cfg = read_case(test_file_name).get('base_info')
        self.url = cfg.get("url", "")
        if self.url == '':
            logger.warning('url为空!!!')
        self.default_headers = cfg.get("headers", {})
        self.client = HttpClient(base_url=base_url)
        logger.info('ApiService初始化成功')


    def _merge_headers(self, headers=None):
        merged = dict(self.default_headers)   # ① 先复制
        if headers:                   # ② None / {} 都跳过
            merged.update(headers)    # ③ 用例传的覆盖同名的
        return merged

    def get(self, headers=None, **kwargs):
        return self.client.get(self.url, headers=self._merge_headers(headers), **kwargs)

    def post(self, headers=None, **kwargs):
        return self.client.post(self.url, headers=self._merge_headers(headers), **kwargs)

    def put(self, headers=None, **kwargs):
        return self.client.put(self.url, headers=self._merge_headers(headers), **kwargs)

    def delete(self, headers=None, **kwargs):
        return self.client.delete(self.url, headers=self._merge_headers(headers), **kwargs)

    def close(self):
        self.client.close()