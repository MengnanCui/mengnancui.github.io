# 第一缕光 · First Light

原创纯钢琴曲，降 A 大调，60 BPM，约 3 分 44 秒。
气质参考 Yiruma《Kiss the Rain》：温柔、朗朗上口、听一遍就记住，带一点"酸"。

- `first_light.mp3`：真钢琴采样渲染
- `first_light.mid`：MIDI，可导入 MuseScore / GarageBand 等
- `final.json`：乐谱（格式见 `score_tools.py`）

## Hook

（吸气）do do do **FA**～ mi ｜ re～ do la——（do = 降A）

三个轻声同音，四度跳上长音 Db。Db 落在 Fm7 的强拍上，和左手形成摩擦，一拍半后半音落下，这就是"酸"的来源。
前奏只唱 do do do FA 不给刺，副歌才第一次刺出来，尾声最后一次落在主和弦上解决回家。

## 创作过程

由多智能体流程完成：

1. 5 位作曲智能体从不同风格独立创作（`candidates/`，试听在 `previews/`）：Yiruma、久石让、韩剧 OST、极简摇篮曲，以及一位先用音乐认知原理设计 hook 的"hook 科学家"
2. 3 位评委（听众、理论、原创性）打分，Yiruma 稿以 8.38 分胜出
3. 主作曲家以胜出稿为骨架，嫁接其它候选的点子
4. 多轮对抗式审查与修改：和声、听感、原创性（修掉了与《平安夜》《My Bonnie》《Danny Boy》相近的片段、中段重复、伴奏 bug 等）

`score_tools.py` 负责校验与分析（拍数、强拍不和谐音是否解决、hook 复现次数等），`render_salamander.py` 负责采样渲染。

## 致谢

钢琴音源：Salamander Grand Piano（Alexander Holm 录制），Accurate Salamander Grand Piano V6.2 版本，CC-BY 3.0。
