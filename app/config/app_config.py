from pydantic import BaseModel, ConfigDict
import os


class AppConfig(BaseModel):

    # allow:允许接收并存储模型中未显式定义的额外属性。frozen=False:意味着实例在创建后可以被修改
    model_config = ConfigDict(extra="allow", frozen=False)


_app_config: AppConfig | None = None


def get_app_config():
    global _app_config
    if _app_config:
        return _app_config
    _app_config = AppConfig(
        channels={
            'langgraph_url': 'http://localhost:2024',
            'gateway_url': 'http://localhost:8001',
            'session': {
                'assistant_id': 'lead_agent',
                'config': {'recursion_limit': 100},
                'context': {
                    # 开启思考模式
                    'thinking_enabled': True,
                    # 启用TodoList中间件
                    'is_plan_mode': False,
                    # 启用子代理委派。
                    'subagent_enabled': False
                }
            },
            'feishu': {
                'enabled': True,
                'app_id': os.getenv('FEISHU_APP_ID'),
                'app_secret': os.getenv('FEISHU_APP_SECRET')}
        }
    )
    return _app_config
