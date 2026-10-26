"""格物 Gewu 的 SVG 渲染与校验工具包。

模块划分：
    textmetrics  文字测量（内置字符宽度表，无外部依赖）
    tokens       视觉设计系统（配色、字号、间距、线宽）
    layout       画布与自动布局原语（分区、节点、连线锚点、自动排版）
    templates    七种图形模板的渲染函数
    validate     SVG 结构与几何校验
    cli          命令行入口
"""

__version__ = "1.0.0"
