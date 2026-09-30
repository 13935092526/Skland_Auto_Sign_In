# -*- coding: utf-8 -*-
"""t2i —— 模板化文字转图片推送工具（基于 Pillow，纯离线）。

对外只提供接口，无命令行：
  render_template(name, data, output)  按模板名渲染出图，返回 PNG 路径
  list_templates()                     全部模板名及所需数据 schema
  push(images, title, text)            推送图片/文字到企业微信 + Server酱

本包作为 utils 库被其他项目引入（无命令行、无 HTTP 服务）；渲染内核（字体/落盘）供模板内部使用。
"""
from __future__ import annotations

from .image_io import save
from .fonts import find_font, load_font
from .registry import get_template, list_templates, render_template
from .notify import push

__version__ = "1.0.0"
__all__ = [
    "render_template", "list_templates", "get_template",
    "push",
    "save", "find_font", "load_font",
]
