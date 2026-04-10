import dataclasses
from datetime import datetime

import os
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from langchain.agents import AgentState
from app.config.app_config import AppConfig
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    try:
        try:
            template = env.get_template(f"{prompt_name}.md")
            return template.render()
        except TemplateNotFound:
            raise ValueError(f"模板 {prompt_name} 不存在。")
    except Exception as e:
        raise ValueError(f"加载模板 {prompt_name} 时出错: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, configurable: AppConfig = None, **kwargs
) -> list:
    try:
        system_prompt = get_system_prompt_template(prompt_name, state, configurable, **kwargs)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")


def get_system_prompt_template(
    prompt_name: str, state: AgentState | None = None, configurable: AppConfig | None = None, **kwargs
) -> str:

    state_vars = {
        # "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        # **state,
    }

    if configurable:
        state_vars.update(dataclasses.asdict(configurable))
    state_vars.update(kwargs)

    try:
        template = env.get_template(prompt_name)
        system_prompt = template.render(**state_vars)
        return system_prompt
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")
