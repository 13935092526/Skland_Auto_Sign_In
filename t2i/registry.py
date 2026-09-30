# -*- coding: utf-8 -*-
"""模板注册表：按名字直接调用渲染，是对外接口的统一入口。

新增模板只需两步：
  1. 在 t2i/templates/ 下建模板文件，提供 validate(data) -> dict 与 render_card(data, output) -> Path
  2. 在本文件 TEMPLATES 里注册一项（含参数 schema 说明）

用法:
  from t2i import render_template, list_templates
  png = render_template("quark_checkin", {"accounts": [...]}, output="out/checkin.png")
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParamSchema:
    """模板所需数据的一个字段说明（用于 /templates 自描述）。"""
    name: str
    type: str          # string / number / integer / array / object
    required: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type,
                "required": self.required, "description": self.description}


@dataclass
class TemplateSpec:
    name: str
    module: str                                  # 模板模块名（t2i/templates/ 下）
    title: str                                   # 默认推送标题
    description: str = ""
    params: list[ParamSchema] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "title": self.title,
                "description": self.description,
                "params": [p.to_dict() for p in self.params]}


TEMPLATES: dict[str, TemplateSpec] = {
    "quark_checkin": TemplateSpec(
        name="quark_checkin", module="quark_checkin", title="夸克网盘签到报告",
        description="夸克网盘每日签到报告卡片（每账号一张卡片，多账号堆叠）",
        params=[
            ParamSchema("accounts", "array", True,
                        "账号列表，每项含 phone(string)、total_cur(number, GB)、"
                        "checkin_cur(number, GB, ≤total_cur)、today_gain(string)、"
                        "streak_done(integer, 0-7)"),
        ],
    ),
    "endfield_checkin": TemplateSpec(
        name="endfield_checkin", module="endfield_checkin", title="终末地签到日历报告",
        description="明日方舟：终末地每日签到报告（每账号一张卡片，卡片内为当月日历式签到表）",
        params=[
            ParamSchema("accounts", "array", True,
                        "账号列表，每项含 nickname(string)、uid(string|integer)、"
                        "hasToday(boolean, 今日是否已签到)、month(string, 选填 YYYY-MM)、"
                        "days_in_month(integer, 选填 28-31)、calendar(array)；"
                        "calendar 每项含 day(integer, 1-31)、signed(boolean)、"
                        "item(string, 选填, 当日签到所得)"),
        ],
    ),
    "klei_weekly": TemplateSpec(
        name="klei_weekly", module="klei_weekly", title="科雷游戏每周掉落报告",
        description="科雷游戏每周掉落 + 今日收获报告卡片",
        params=[
            ParamSchema("deadline", "string", True, "本周掉落截止时间，ISO 格式如 2026-10-01T18:00:00"),
            ParamSchema("games", "array", True,
                        "游戏列表，每项含 name(string)、weekly_done(integer)、"
                        "weekly_total(integer, 1-12)"),
            ParamSchema("gifts", "array", True,
                        "当天收获礼物（可为空数组），每项含 item(string)、game(string，"
                        "须出现在 games 中)、kind(string, 每日|每周)、time(string)"),
        ],
    ),
}


def list_templates() -> list[dict]:
    """全部已注册模板及其参数 schema，供调用方自描述。"""
    return [t.to_dict() for t in TEMPLATES.values()]


def get_template(name: str) -> TemplateSpec:
    spec = TEMPLATES.get(name)
    if spec is None:
        raise KeyError(f"未知模板 {name!r}，可用: {', '.join(sorted(TEMPLATES))}")
    return spec


def render_template(name: str, data: dict, output: str | Path) -> Path:
    """按模板名渲染：校验数据 -> 出图，返回 PNG 路径。数据不合法时抛 ValueError。"""
    spec = get_template(name)
    mod = importlib.import_module(f"t2i.templates.{spec.module}")
    return mod.render_card(mod.validate(data), output)
