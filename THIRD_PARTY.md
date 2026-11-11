# 示例 Skill 来源

## Qwen Image 2.1

- 原项目：[iamyoki/qwen-image-2.1-skill](https://github.com/iamyoki/qwen-image-2.1-skill)。这是基于 Qwen 官方提示词规范整理的社区 skill，不是阿里官方发布的 skill。
- 本仓库 `skills/qwen-image-2-1` 保留上游文件内容，来源版本：[`32b8100e70299b56478a35a9f1d5703605cdba46`](https://github.com/iamyoki/qwen-image-2.1-skill/tree/32b8100e70299b56478a35a9f1d5703605cdba46/skills/qwen-image-2-1-prompter)。仅将安装文件夹命名为 `qwen-image-2-1`，并附上原项目 LICENSE。
- 作者：iamyoki。上游说明中提示词规则归 Alibaba Qwen Team 所有。许可：[Apache-2.0](skills/qwen-image-2-1/LICENSE)，保留原许可与版权声明，不受本插件 MIT 许可替代。

## MiniMax H3

- 官方来源：[MiniMax-AI/MiniMax-H3 — h3-prompt-writing](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)。
- 安装脚本固定来源版本：[`199b7d0e1fd95e7b3eafa8c15eca692534142427`](https://github.com/MiniMax-AI/MiniMax-H3/tree/199b7d0e1fd95e7b3eafa8c15eca692534142427/skills/h3-prompt-writing)，安装前验证每个文件的 SHA-256。
- 官方仓库指向 [MiniMax H3 Community License Agreement](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)，包含地域和分发条件。官方文档不随本公开仓库重新分发；`scripts/install_h3_skill.py` 由用户运行，从官方地址下载并在本地保留 LICENSE 和 NOTICE。
- 本地安装结果为 `skills/h3-prompt-writing`，仍被 Git 忽略。安装脚本不会覆盖已有的不同内容。

插件代码与原有基础 `example-image`、`example-video` skill 使用根目录 MIT 许可。用户另行添加的其他 skill 保留各自许可。
