"""QQ空间纯文字说说工具及持久化概率调度。"""
import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from maibot_sdk import MaiBotPlugin, PluginConfigBase, Field, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

TZ = timezone(timedelta(hours=8))
API = 'maibot-team.snowluma-adapter.adapter.napcat.qzone.send_qzone_msg'

class PluginSettings(PluginConfigBase):
    config_version: str = Field(default='1.0.0', description='配置版本')
    enabled: bool = Field(default=True, description='启用插件')

class AutoSettings(PluginConfigBase):
    enabled: bool = Field(default=True, description='允许自主发说说')
    probability: float = Field(default=0.2, ge=0, le=1, description='每小时触发概率')
    start_hour: int = Field(default=9, ge=0, le=23, description='开始小时，包含，上海时间')
    end_hour: int = Field(default=23, ge=1, le=24, description='结束小时，不包含，上海时间')
    cooldown_hours: float = Field(default=4, ge=1, description='自主发布最小间隔小时')
    daily_limit: int = Field(default=2, ge=0, le=24, description='每天自主发布尝试上限，失败也占用额度以避免重复')

class Settings(PluginConfigBase):
    plugin: PluginSettings = Field(default_factory=PluginSettings)
    autonomous: AutoSettings = Field(default_factory=AutoSettings)
    visibility: int = Field(default=1, description='空间可见性：1所有人，4好友，64仅自己')

class QzonePlugin(MaiBotPlugin):
    config_model = Settings

    def __init__(self):
        super().__init__()
        self.state = {}
        self.lock = asyncio.Lock()
        self.task = None

    @property
    def state_path(self):
        return self.ctx.paths.data_dir / 'schedule_state.json'

    def load_state(self):
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('说说调度状态文件损坏')
            self.state = data

    def save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        tmp.replace(self.state_path)

    async def on_load(self):
        self.load_state()
        # 新安装不立即抽签；从下一个整点开始，重启不重复抽当前小时。
        if not self.state.get('slot'):
            self.state['slot'] = datetime.now(TZ).strftime('%Y-%m-%d %H')
            self.save_state()
        self.task = asyncio.create_task(self.scheduler())
        self.ctx.logger.info('说说插件已加载：手动工具及上海时间每小时概率调度')

    async def on_unload(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def on_config_update(self, new_config):
        self.set_plugin_config(new_config)

    async def scheduler(self):
        while True:
            await asyncio.sleep(30)
            try:
                result = await self.tick(datetime.now(TZ))
                if result.get('attempted'):
                    self.ctx.logger.info('自主说说发布结果：%s', result)
            except Exception:
                self.ctx.logger.exception('说说调度失败，本轮结束，不自动补发')

    async def generate_text(self, topic=''):
        persona = await self.ctx.config.get('personality.personality', '')
        prompt = [
            {'role': 'system', 'content': str(persona or '你是麦麦。') + '\n为自己的QQ空间写一条30至120字的纯文字说说，只输出正文。写日常感想，不虚构真实经历或现实行动，不包含他人隐私，不引用聊天记录。不输出推理、标题或说明。'},
            {'role': 'user', 'content': '上海时间：' + datetime.now(TZ).strftime('%Y-%m-%d %H:%M') + '\n主题：' + (topic or '随心的日常小感想，避免与最近说说重复。') + '\n最近自己发布的正文，仅用于避免重复：' + str(self.state.get('recent', []))}]
        result = await self.ctx.llm.generate(prompt=prompt, task_name='replyer', max_tokens=400, temperature=0.9)
        if not isinstance(result, dict) or result.get('success') is False:
            raise ValueError('说说正文生成失败，尚未发布')
        text = str(result.get('response') or '').strip()
        if not text or len(text) > 1000 or '<think' in text:
            raise ValueError('生成正文为空、过长或包含推理标记，尚未发布')
        return text

    async def publish(self, content):
        if self.config.visibility not in (1, 4, 64):
            return {'success': False, 'error': 'visibility仅支持1、4、64'}
        response = await self.ctx.api.call(API, params={'content': content, 'ugc_right': self.config.visibility})
        if not isinstance(response, dict) or response.get('success') is False or response.get('status', 'ok') != 'ok' or response.get('retcode', 0) not in (0, 1):
            return {'success': False, 'error': str(response), 'content': '发布失败或未确认，请勿自动重试'}
        data = response.get('data')
        tid = data.get('tid') if isinstance(data, dict) else None
        if not tid:
            return {'success': False, 'error': '没有收到说说tid，发布未确认；可能已发出，请勿自动重试'}
        self.state['recent'] = (self.state.get('recent', []) + [content])[-5:]
        self.save_state()
        return {'success': True, 'tid': str(tid), 'content': 'QQ空间说说发布成功', 'text': content}

    @Tool('publish_qzone', description='用户明确要求发QQ空间说说时调用。content为原文；如果用户要求你构思说说，则传topic主题并留空content。不得在普通聊天中擅自调用，自主说说由插件定时处理。根据success报告结果，失败或未确认不得声称成功或自动重发。', parameters=[
        ToolParameterInfo(name='content', param_type=ToolParamType.STRING, description='明确要发布的纯文字正文，与topic至少一项', required=False),
        ToolParameterInfo(name='topic', param_type=ToolParamType.STRING, description='让麦麦构思说说的主题，提供content时忽略此项', required=False)])
    async def publish_qzone(self, content='', topic='', **kwargs):
        async with self.lock:
            try:
                if not self.config.plugin.enabled:
                    return {'success': False, 'error': '插件已关闭'}
                if not isinstance(content, str) or not isinstance(topic, str):
                    return {'success': False, 'error': '正文和主题必须为文字'}
                text = content.strip()
                if not text:
                    if not topic.strip():
                        return {'success': False, 'error': '请提供正文或构思主题'}
                    text = await self.generate_text(topic.strip())
                if len(text) > 1000:
                    return {'success': False, 'error': '仅支持1至1000字的纯文字说说'}
                return await self.publish(text)
            except Exception as exc:
                return {'success': False, 'error': str(exc), 'content': '未确认发布，不要自动重发'}

    async def tick(self, now, draw=None):
        async with self.lock:
            cfg = self.config.autonomous
            now = now.astimezone(TZ)
            if not self.config.plugin.enabled or not cfg.enabled:
                return {'success': False}
            slot = now.strftime('%Y-%m-%d %H')
            if slot == self.state.get('slot'):
                return {'success': False}
            self.state['slot'] = slot
            self.save_state()
            day = now.strftime('%Y-%m-%d')
            count = self.state.get('count', 0) if self.state.get('day') == day else 0
            if not cfg.start_hour <= now.hour < cfg.end_hour or count >= cfg.daily_limit:
                return {'success': False}
            if now.timestamp() - self.state.get('last_attempt', 0) < cfg.cooldown_hours * 3600:
                return {'success': False}
            if (random.random() if draw is None else draw) >= cfg.probability:
                return {'success': False}
            # 发送前持久化额度，异常、断线和重启均不导致重复尝试。
            self.state.update(day=day, count=count + 1, last_attempt=now.timestamp())
            self.save_state()
            try:
                text = await self.generate_text()
                if text in self.state.get('recent', []):
                    return {'success': False, 'attempted': True, 'error': '正文重复，本轮跳过'}
                result = await self.publish(text)
                result['attempted'] = True
                return result
            except Exception as exc:
                return {'success': False, 'attempted': True, 'error': str(exc)}

def create_plugin():
    return QzonePlugin()


