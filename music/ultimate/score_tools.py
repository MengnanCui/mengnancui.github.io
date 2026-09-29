"""
乐谱工具箱：统一的乐谱 JSON 格式 + 校验 + 分析 + 编配成音符事件 + 导出 MIDI

用法：
    python3 score_tools.py score.json            # 校验 + 分析报告
    python3 score_tools.py score.json --midi x.mid

乐谱 JSON 格式（4/4 拍）：
{
  "title": "English title", "title_zh": "中文名",
  "bpm": 64,
  "key": "Ab major",
  "hook": {"section": 1, "bar": 0, "notes": 5,        # 核心动机：第几段、第几小节开始、取前几个音
           "description": "..."},
  "ending": {"ritardando_bars": 3},
  "sections": [
    {"name": "Intro", "dynamic": 0.35, "accomp": "arp8",
     "melody_octave_double": false, "transpose": 0,
     "bars": [
        {"chords": ["Dbmaj7"],                        # 1 个 = 整小节；2 个 = 前后各半小节
         "melody": [["F5", 0.5], ["rest", 0.5], ["Ab5", 1.5], ["G5", 1.5]],
         "counter": [["C5", 2], ["Bb4", 2]],          # 可选：内声部/副旋律（每小节同样须满 4 拍）
         "dyn": 1.0,                                  # 可选：本小节力度倍数（做渐强渐弱）
         "accomp": "pad"}                             # 可选：本小节伴奏型覆盖
     ]}
  ]
}
dynamic 取 0..1，映射到 MIDI 力度约 20..110。温柔的曲子大部分应在 0.25..0.6。

伴奏型（左手，按和弦自动生成开放式排列：根音-五度-色彩音-十度-高五度）：
  none      不弹
  pad       小节开头轻轻琶音式按下整个和弦并保持
  sparse    四分音符 根-五-色彩-十度
  arp8      八分音符 根 五 色 十 高 十 色 五
  arp8_wave 八分音符 根 五 色 十 色 十 高 十
  triplet   八分三连音 根 五 十 高 十 五 ...
  arp16     十六分音符
和弦品质：'' m maj7 m7 7 sus4 sus2 add9 madd9 maj9 m9 6 m6 dim m7b5，可加 /低音
"""
import json
import re
import sys

PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4, 'E#': 5,
      'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10,
      'Bb': 10, 'B': 11, 'Cb': 11, 'B#': 0}

# 品质 -> (三度, 色彩音, 其它和弦音)   色彩音是左手开放排列里的第三个音
QUALITIES = {
    '':      (4, 14, [0, 4, 7]),
    'add9':  (4, 14, [0, 4, 7, 2]),
    'm':     (3, 12, [0, 3, 7]),
    'madd9': (3, 14, [0, 3, 7, 2]),
    'maj7':  (4, 11, [0, 4, 7, 11]),
    'maj9':  (4, 14, [0, 4, 7, 11, 2]),
    'm7':    (3, 10, [0, 3, 7, 10]),
    'm9':    (3, 14, [0, 3, 7, 10, 2]),
    '7':     (4, 10, [0, 4, 7, 10]),
    'sus4':  (5, 14, [0, 5, 7, 2]),
    'sus2':  (2, 12, [0, 2, 7]),
    '6':     (4, 9, [0, 4, 7, 9]),
    'm6':    (3, 9, [0, 3, 7, 9]),
    'dim':   (3, 12, [0, 3, 6]),
    'm7b5':  (3, 10, [0, 3, 6, 10]),
}
ACCOMPS = {'none', 'pad', 'sparse', 'arp8', 'arp8_wave', 'triplet', 'arp16'}
EPS = 1e-6


def note_num(name):
    m = re.fullmatch(r'([A-G](?:#|b)?)(-?\d)', name)
    if not m or m.group(1) not in PC:
        raise ValueError(f'无法识别的音名: {name}')
    return 12 * (int(m.group(2)) + 1) + PC[m.group(1)]


def parse_chord(sym):
    m = re.fullmatch(r'([A-G](?:#|b)?)([a-z0-9]*)(?:/([A-G](?:#|b)?))?', sym)
    if not m or m.group(1) not in PC:
        raise ValueError(f'无法识别的和弦: {sym}')
    root, qual, slash = m.group(1), m.group(2), m.group(3)
    if qual not in QUALITIES:
        raise ValueError(f'和弦 {sym} 的品质 "{qual}" 不在支持列表 {sorted(QUALITIES)}')
    if slash and slash not in PC:
        raise ValueError(f'和弦 {sym} 的低音无法识别')
    third, color, tones = QUALITIES[qual]
    r = PC[root]
    pcs = {(r + t) % 12 for t in tones}
    ar = 38 + (r - 38) % 12                 # 左手和弦根音 D2..C#3
    bass = ar
    if slash:
        bass = 33 + (PC[slash] - 33) % 12   # A1..G#2
        if bass >= ar:
            bass -= 12
        pcs.add(PC[slash])
    voicing = [bass, ar + 7, ar + color, ar + 12 + third, ar + 19]
    return {'root': r, 'pcs': pcs, 'voicing': voicing, 'bass': bass}


# ---------------------------------------------------------------- 校验
def validate(score):
    errs = []
    if not (40 <= score.get('bpm', 0) <= 120):
        errs.append('bpm 应在 40..120')
    secs = score.get('sections', [])
    if not secs:
        errs.append('没有 sections')
    for si, sec in enumerate(secs):
        tag = f'段{si}({sec.get("name")})'
        if sec.get('accomp', 'arp8') not in ACCOMPS:
            errs.append(f'{tag}: 未知伴奏型 {sec.get("accomp")}')
        if not (0 < sec.get('dynamic', 0.5) <= 1):
            errs.append(f'{tag}: dynamic 应在 (0,1]')
        if not sec.get('bars'):
            errs.append(f'{tag}: 没有小节')
        for bi, bar in enumerate(sec.get('bars', [])):
            btag = f'{tag} 小节{bi}'
            ch = bar.get('chords')
            if not isinstance(ch, list) or len(ch) not in (1, 2):
                errs.append(f'{btag}: chords 必须是 1 或 2 个和弦的列表')
            else:
                for c in ch:
                    try:
                        parse_chord(c)
                    except ValueError as e:
                        errs.append(f'{btag}: {e}')
            if bar.get('accomp') and bar['accomp'] not in ACCOMPS:
                errs.append(f'{btag}: 未知伴奏型 {bar["accomp"]}')
            for voice in ('melody', 'counter'):
                if voice == 'counter' and voice not in bar:
                    continue
                notes = bar.get(voice)
                if not isinstance(notes, list) or not notes:
                    errs.append(f'{btag}: {voice} 为空')
                    continue
                tot = 0
                for item in notes:
                    if not (isinstance(item, list) and len(item) == 2):
                        errs.append(f'{btag}: {voice} 音符格式应为 [音名, 拍数]: {item}')
                        continue
                    p, d = item
                    if not isinstance(d, (int, float)) or d <= 0:
                        errs.append(f'{btag}: 时值非法 {item}')
                        continue
                    tot += d
                    if p != 'rest':
                        try:
                            m = note_num(p)
                            lo, hi = (55, 96) if voice == 'melody' else (50, 84)
                            if not lo <= m <= hi:
                                errs.append(f'{btag}: {voice} 音 {p} 超出建议音域')
                        except ValueError as e:
                            errs.append(f'{btag}: {e}')
                if abs(tot - 4) > EPS:
                    errs.append(f'{btag}: {voice} 总时值 {tot} 拍，应为 4 拍')
    h = score.get('hook')
    if h:
        try:
            secs[h['section']]['bars'][h['bar']]
        except (KeyError, IndexError, TypeError):
            errs.append('hook 指向的段/小节不存在')
    return errs


# ---------------------------------------------------------------- 编配
def bar_chord_at(bar, beat_in_bar):
    ch = bar['chords']
    return ch[0] if len(ch) == 1 or beat_in_bar < 2 - EPS else ch[1]


def accomp_notes(pattern, voicing, start, span):
    b, five, col, ten, top = voicing
    out = []   # (起始拍, 时值, midi, 相对力度)
    end = start + span
    if pattern == 'none':
        return out
    if pattern == 'pad':
        for k, m in enumerate([b, five, col, ten]):
            s = start + 0.06 * k
            out.append((s, end - s, m, 0.8 if k == 0 else 0.6))
        return out
    seqs = {
        'sparse':    ([b, five, col, ten], 1.0),
        'arp8':      ([b, five, col, ten, top, ten, col, five], 0.5),
        'arp8_wave': ([b, five, col, ten, col, ten, top, ten], 0.5),
        'triplet':   ([b, five, ten, top, ten, five], 1 / 3),
        'arp16':     ([b, five, col, ten, top, ten, col, five], 0.25),
    }
    seq, step = seqs[pattern]
    count = int(round(span / step))
    for k in range(count):
        # 循环回到开头时照常重弹根音（原先换成五音，会让 triplet/arp16 在小节中间连弹三次同一个五音）
        m = seq[k % len(seq)]
        s = start + k * step
        out.append((s, end - s, m, 1.0 if k == 0 else 0.72))
    return out


def arrange(score):
    """-> events: dict(start, dur, midi, vel(0..1), voice in melody/counter/accomp)"""
    events = []
    beat = 0.0
    for sec in score['sections']:
        tr = sec.get('transpose', 0)
        base = sec.get('dynamic', 0.5)
        for bar in sec['bars']:
            dyn = base * bar.get('dyn', 1.0)
            pattern = bar.get('accomp', sec.get('accomp', 'arp8'))
            for voice, scale in (('melody', 1.0), ('counter', 0.62)):
                t = beat
                for p, d in bar.get(voice, []):
                    if p != 'rest':
                        m = note_num(p) + tr
                        shape = 1.0 + 0.004 * (m - 72) + (0.05 if d >= 1.5 else 0)
                        v = min(dyn * scale * shape, 1.0)
                        events.append(dict(start=t, dur=d, midi=m, vel=v, voice=voice))
                        if voice == 'melody' and sec.get('melody_octave_double'):
                            events.append(dict(start=t, dur=d, midi=m - 12, vel=v * 0.5,
                                               voice='counter'))
                    t += d
            chords = bar['chords']
            span = 4 / len(chords)
            for h, sym in enumerate(chords):
                v = parse_chord(sym)['voicing']
                for s, d, m, rel in accomp_notes(pattern, v, beat + span * h, span):
                    events.append(dict(start=s, dur=d, midi=m + tr,
                                       vel=dyn * 0.5 * rel, voice='accomp'))
            beat += 4
    return events, beat


def total_seconds(score):
    _, beats = arrange(score)
    rit = score.get('ending', {}).get('ritardando_bars', 0) * 4
    sec = beats * 60 / score['bpm']
    return sec + rit * 60 / score['bpm'] * 0.3


# ---------------------------------------------------------------- 分析
def melody_stream(score):
    """扁平化旋律: (段, 小节, 拍位, midi, 时值, 当拍和弦 pcs)"""
    out = []
    for si, sec in enumerate(score['sections']):
        tr = sec.get('transpose', 0)
        for bi, bar in enumerate(sec['bars']):
            t = 0
            for p, d in bar['melody']:
                if p != 'rest':
                    ch = parse_chord(bar_chord_at(bar, t))
                    pcs = {(x + tr) % 12 for x in ch['pcs']}
                    out.append((si, bi, t, note_num(p) + tr, d, pcs))
                t += d
    return out


def hook_signature(score):
    h = score.get('hook')
    if not h:
        return None
    stream = melody_stream(score)
    idx = next((i for i, x in enumerate(stream) if x[0] == h['section'] and x[1] == h['bar']), None)
    if idx is None:
        return None
    k = h.get('notes', 5)
    seg = stream[idx:idx + k]
    return [b[3] - a[3] for a, b in zip(seg, seg[1:])], [x[4] for x in seg[:-1]]


def find_hook(score):
    sig = hook_signature(score)
    if not sig:
        return [], []
    ivs, rhy = sig
    stream = melody_stream(score)
    exact, contour = [], []
    k = len(ivs) + 1
    sgn = lambda x: (x > 0) - (x < 0)
    for i in range(len(stream) - k + 1):
        seg = stream[i:i + k]
        iv = [b[3] - a[3] for a, b in zip(seg, seg[1:])]
        r = [x[4] for x in seg[:-1]]
        if r != rhy:
            continue
        loc = (seg[0][0], seg[0][1], seg[0][2])
        if iv == ivs:
            exact.append(loc)
        elif [sgn(x) for x in iv] == [sgn(x) for x in ivs]:
            contour.append(loc)
    return exact, contour


def analyze(score):
    events, beats = arrange(score)
    stream = melody_stream(score)
    rep = {}
    rep['bars'] = int(beats // 4)
    rep['seconds_approx'] = round(total_seconds(score), 1)
    mel = [x[3] for x in stream]
    rep['melody_range'] = (min(mel), max(mel))
    peak = max(stream, key=lambda x: x[3])
    rep['climax_at'] = f'段{peak[0]} 小节{peak[1]}'
    # 强拍不和谐音及其解决
    sus, unresolved = [], []
    for i, (si, bi, t, m, d, pcs) in enumerate(stream):
        if abs(t % 2) > EPS or (m % 12) in pcs:
            continue
        nxt = stream[i + 1] if i + 1 < len(stream) else None
        where = f'段{si}小节{bi}拍{t:g}'
        if nxt and 1 <= abs(nxt[3] - m) <= 2 and (nxt[3] % 12) in nxt[5]:
            sus.append(where)
        else:
            unresolved.append(where)
    rep['strong_beat_dissonances_resolved'] = sus
    rep['strong_beat_dissonances_unresolved'] = unresolved
    # 旋律与伴奏同时发声的小二度/大七度撞音（同一八度内）
    acc = [e for e in events if e['voice'] == 'accomp']
    clashes = 0
    for e in events:
        if e['voice'] != 'melody':
            continue
        for a in acc:
            if a['start'] < e['start'] + EPS and a['start'] + min(a['dur'], 1.0) > e['start'] + EPS:
                if abs(e['midi'] - a['midi']) in (1, 2) and e['start'] - a['start'] < 0.5:
                    clashes += 1
    rep['melody_accomp_close_clashes'] = clashes
    leaps = [abs(b[3] - a[3]) for a, b in zip(stream, stream[1:])]
    rep['leaps_over_octave'] = sum(1 for x in leaps if x > 12)
    rep['stepwise_ratio'] = round(sum(1 for x in leaps if x <= 2) / max(len(leaps), 1), 2)
    durs = [x[4] for x in stream]
    rep['sixteenth_or_faster_ratio'] = round(sum(1 for x in durs if x <= 0.25 + EPS) / len(durs), 2)
    rep['avg_section_dynamic'] = round(sum(s.get('dynamic', .5) for s in score['sections'])
                                       / len(score['sections']), 2)
    ex, ct = find_hook(score)
    rep['hook_exact_recurrences'] = len(ex)
    rep['hook_contour_recurrences'] = len(ct)
    rep['hook_locations'] = [f'段{a}小节{b}拍{c:g}' for a, b, c in ex + ct]
    return rep


def write_midi(score, path):
    import mido
    events, _ = arrange(score)
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(score['bpm'])))
    tr.append(mido.MetaMessage('track_name', name=score.get('title', 'piano')))
    msgs = []
    for e in events:
        vel = int(20 + 90 * e['vel'])
        msgs.append((int(e['start'] * 480), 1, e['midi'], vel))
        msgs.append((int((e['start'] + e['dur']) * 480), 0, e['midi'], 0))
    msgs.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, on, m, vel in msgs:
        tr.append(mido.Message('note_on' if on else 'note_off', note=m,
                               velocity=vel, time=tick - last))
        last = tick
    mid.save(path)


if __name__ == '__main__':
    path = sys.argv[1]
    with open(path) as f:
        score = json.load(f)
    errs = validate(score)
    if errs:
        print('校验失败:')
        for e in errs:
            print('  -', e)
        sys.exit(1)
    print('校验通过')
    for k, v in analyze(score).items():
        print(f'{k}: {v}')
    if '--midi' in sys.argv:
        write_midi(score, sys.argv[sys.argv.index('--midi') + 1])
        print('MIDI 已写出')
