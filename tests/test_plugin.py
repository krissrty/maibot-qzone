import importlib.util
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
class QzoneTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('qzone', ROOT / 'plugin.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.p = module.create_plugin()
        self.p.set_plugin_config({'plugin': {'config_version': '1.0.0'}})
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        self.response = {'status': 'ok', 'retcode': 0, 'data': {'tid': 'abc'}}
        async def call(name, **kwargs):
            self.calls.append((name, kwargs))
            return self.response
        async def generate(**kwargs):
            return {'success': True, 'response': '今天也是元气满满的一天。' + str(len(self.calls))}
        async def config_get(*args):
            return '你是麦麦。'
        self.p._ctx = SimpleNamespace(paths=SimpleNamespace(data_dir=pathlib.Path(self.tmp.name)), api=SimpleNamespace(call=call), llm=SimpleNamespace(generate=generate), config=SimpleNamespace(get=config_get))
        self.now = datetime(2026, 10, 18, 10, tzinfo=timezone(timedelta(hours=8)))

    async def test_manual_plain_text(self):
        r = await self.p.publish_qzone('早安')
        self.assertTrue(r['success'])
        self.assertEqual(self.calls[-1][1]['params'], {'content': '早安', 'ugc_right': 1})

    async def test_generate_from_topic(self):
        self.assertTrue((await self.p.publish_qzone(topic='开心'))['success'])

    async def test_failure_and_no_receipt(self):
        for response in (None, {'success': False}, {'status': 'failed'}, {'status': 'ok', 'data': {}}):
            self.response = response
            self.assertFalse((await self.p.publish_qzone('你好'))['success'])

    async def test_hour_is_only_sampled_once_and_persisted(self):
        self.assertTrue((await self.p.tick(self.now, draw=0))['success'])
        self.assertFalse((await self.p.tick(self.now, draw=0))['success'])
        self.p.state = {}
        self.p.load_state()
        self.assertFalse((await self.p.tick(self.now, draw=0))['success'])
        self.assertEqual(len(self.calls), 1)

    async def test_quiet_hours_probability_cooldown_daily_cap(self):
        self.assertFalse((await self.p.tick(self.now.replace(hour=3), draw=0))['success'])
        self.assertFalse((await self.p.tick(self.now, draw=0.9))['success'])
        self.assertTrue((await self.p.tick(self.now.replace(hour=11), draw=0))['success'])
        self.assertFalse((await self.p.tick(self.now.replace(hour=12), draw=0))['success'])
        self.assertTrue((await self.p.tick(self.now.replace(hour=15), draw=0))['success'])
        self.assertFalse((await self.p.tick(self.now.replace(hour=20), draw=0))['success'])
        self.assertEqual(len(self.calls), 2)

    async def test_failed_auto_attempt_is_not_retried_after_restart(self):
        self.response = {'success': False}
        self.assertFalse((await self.p.tick(self.now, draw=0))['success'])
        self.p.state = {}
        self.p.load_state()
        self.assertFalse((await self.p.tick(self.now.replace(hour=11), draw=0))['success'])
        self.assertEqual(len(self.calls), 1)

    async def test_daily_quota_resets_next_day(self):
        await self.p.tick(self.now, draw=0)
        await self.p.tick(self.now.replace(hour=15), draw=0)
        self.assertTrue((await self.p.tick(self.now.replace(day=19), draw=0))['success'])

    async def test_empty_manual_request_does_not_publish(self):
        self.assertFalse((await self.p.publish_qzone())['success'])
        self.assertEqual(self.calls, [])

    async def test_disabled_no_api(self):
        self.p.set_plugin_config({'plugin': {'config_version': '1.0.0'}, 'autonomous': {'enabled': False}})
        self.assertFalse((await self.p.tick(self.now, draw=0))['success'])
        self.assertEqual(self.calls, [])

if __name__ == '__main__':
    unittest.main()



