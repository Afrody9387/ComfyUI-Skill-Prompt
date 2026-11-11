# 提示词 Skills

图片示例默认使用随包提供的 `qwen-image-2-1`。视频示例默认使用 `h3-prompt-writing`，在插件目录执行 `python scripts/install_h3_skill.py` 从官方安装。来源与许可见 [THIRD_PARTY.md](../THIRD_PARTY.md)。

将完整的 skill 文件夹放在这里，每个 skill 一个子文件夹：

```text
skills/
  qwen-image-2-1-prompter/
    SKILL.md
    references/
      t2i_rules.md
      edit_rules.md
  my-prompt-skill/
    SKILL.md
```

Skill Prompt Generator 只从本插件的此目录读取 skill，下拉菜单显示子文件夹名称。
添加或删除 skill 后刷新 ComfyUI 浏览器页面；修改现有文件内容后直接重新运行即可。
请保留 skill 自带的参考资料和许可文件。节点读取文档规则，不执行脚本或工具。
