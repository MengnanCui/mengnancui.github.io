"""
《想念的形状》(The Shape of Missing You) —— 原创钢琴曲，第二版

这一版专门针对"记忆点"(hook)来写：
  1. 核心动机 —— 短-长(切分)-长音-回落：  ♪ ♩ ♩.(落在反拍) ♪ ♪
     长音刻意落在和弦的大七度 / 七度上（不和谐），再往下解决 —— 这就是"揪心、酸"的来源。
  2. 模进 —— 同一个形状沿"王道进行" IV–V–iii–vi 逐级下移，听两遍就能跟着哼。
  3. 借用小四级 (D → Dm) —— 大调里突然出现的那个小和弦，是抒情曲最常用的"酸点"。
  4. 最后一遍副歌升全音转调 (A → B)，情绪再推一层。
  5. 左手用 Yiruma 式开放分解和弦：根音-五度-九度/七度-十度。

结构：前奏(动机预告) - 主歌 - 副歌 - 间奏(动机回声) - 桥段 - 副歌(升调) - 尾声
A 大调，4/4，76 BPM
"""
import re
import numpy as np
import mido
import lameenc
from scipy.signal import fftconvolve

SR = 44100
BPM = 76
BEAT = 60.0 / BPM
rng = np.random.default_rng(11)

PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
      'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}


def n(name):
    m = re.match(r'([A-G][#b]?)(-?\d)', name)
    return 12 * (int(m.group(2)) + 1) + PC[m.group(1)]


def chord_tones(sym):
    """和弦符号 -> (低音, [五度, 色彩音, 十度, 高五度])，开放式钢琴左手排列"""
    m = re.match(r'([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$', sym)
    root, qual, slash = m.group(1), m.group(2), m.group(3)
    third = 3 if (qual.startswith('m') and not qual.startswith('maj')) else 4
    if 'sus4' in qual:
        third = 5
    if qual == 'maj7':
        color = 11
    elif qual.endswith('7'):
        color = 10
    elif 'add9' in qual or qual in ('', 'sus4'):
        color = 14          # 大三和弦默认加九度，清亮
    else:
        color = 12          # 小三和弦用八度，保持干净
    r = PC[root]
    ar = 38 + (r - 38) % 12              # 左手和弦根音放在 D2..C#3
    bass = ar
    if slash:
        bass = 34 + (PC[slash] - 34) % 12
        if bass > ar:
            bass -= 12
    return bass, [ar + 7, ar + color, ar + 12 + third, ar + 19]


# ---------- 旋律（A 大调书写）----------
# 核心动机 H(x)：短 - 长(切分进入) - 附点长音(落在反拍，七度音) - 回落两个八分
HOOK_CHORUS = [
    [('F#5', .5), ('A5', 1), ('C#6', 1.5), ('B5', .5), ('A5', .5)],   # Dmaj7：C# 是大七度
    [('B5', 1.5), ('G#5', .5), ('E5', 2)],                            # E
    [('E5', .5), ('G#5', 1), ('B5', 1.5), ('A5', .5), ('G#5', .5)],   # C#m7：同形下移（模进）
    [('A5', 1.5), ('F#5', .5), ('C#5', 2)],                           # F#m
    [('D5', .5), ('F#5', 1), ('A5', 1.5), ('B5', .5), ('C#6', .5)],   # Bm7：第三次，这次往上冲
    [('E6', 2), ('D6', .5), ('C#6', .5), ('B5', 1)],                  # Esus4 → E：全曲最高点
    [('C#6', 1.5), ('B5', .5), ('A5', 1), ('E5', 1)],                 # A/C#
    [('F#5', 1), ('A5', 1), ('G#5', 2)],                              # D → E
]
CHORUS_CHORDS = ['Dmaj7', 'E', 'C#m7', 'F#m', 'Bm7', ['Esus4', 'E'], 'A/C#', ['D', 'E']]

# 主歌：同音反复 + 小回落，也是逐级下移的模进
VERSE = [
    [('C#5', .5), ('C#5', .5), ('C#5', .5), ('D5', .5), ('E5', 1.5), ('C#5', .5)],
    [('B4', .5), ('B4', .5), ('B4', .5), ('C#5', .5), ('B4', 1), ('G#4', 1)],
    [('A4', .5), ('A4', .5), ('A4', .5), ('B4', .5), ('C#5', 1.5), ('A4', .5)],
    [('B4', 1.5), ('G#4', .5), ('E4', 2)],
    [('D5', .5), ('E5', .5), ('F#5', 1.5), ('E5', .5), ('D5', 1)],
    [('C#5', .5), ('D5', .5), ('E5', 1.5), ('D5', .5), ('C#5', 1)],
    [('B4', .5), ('C#5', .5), ('D5', 1), ('F#5', 1), ('A5', 1)],
    [('A5', 2), ('G#5', 1.5), (None, .5)],                            # 挂四 → 解决
]
VERSE_CHORDS = ['A', 'E/G#', 'F#m', 'C#m/E', 'D', 'A/C#', 'Bm7', ['Esus4', 'E']]

# 前奏：动机先"预告"一次（八音盒一样的高音区）
INTRO = [
    [(None, .5), ('F#6', .5), ('A6', 1), ('C#7', 1.5), ('B6', .5)],
    [('B6', 1.5), ('G#6', .5), ('E6', 2)],
    [(None, .5), ('E6', .5), ('G#6', 1), ('B6', 1.5), ('A6', .5)],
    [('A6', 1.5), ('F#6', .5), ('C#6', 2)],
]
INTRO_CHORDS = ['Dmaj7', 'E', 'C#m7', 'F#m']

# 间奏：动机在中音区的回声
INTERLUDE = [
    [('C#5', .5), ('E5', 1), ('A5', 1.5), ('G#5', .5), ('F#5', .5)],
    [('F#5', 2), ('E5', 1), ('C#5', 1)],
    [('E5', .5), ('A5', 1), ('C#6', 1.5), ('B5', .5), ('A5', .5)],
    [('B5', 3), (None, 1)],
]
INTERLUDE_CHORDS = ['F#m', 'D', 'A', 'E']

# 桥段：拉长音、往上爬，最后落到 F#（B 大调的属和弦）准备转调
BRIDGE = [
    [('A5', 1.5), ('G#5', .5), ('F#5', 1), ('C#5', 1)],
    [('E5', 1.5), ('F#5', .5), ('G#5', 2)],
    [('A5', 1.5), ('B5', .5), ('C#6', 1), ('D6', 1)],
    [('B5', 1), ('E6', 1), ('C#6', 1.5), ('A#5', .5)],
]
BRIDGE_CHORDS = ['F#m', 'C#m', 'Dmaj7', ['E', 'F#']]

# 尾声（随最后副歌一起升到 B 大调）：动机最后一次，借用小四级收尾
OUTRO = [
    [('F#5', .5), ('A5', 1), ('C#6', 1.5), ('B5', .5), ('A5', .5)],
    [('B5', 1.5), ('G#5', .5), ('E5', 2)],
    [('F#5', 2), ('F5', 2)],                                          # D → Dm：F 还原，最"酸"的一下
    [('C#5', .5), ('E5', .5), ('A5', 3)],
]
OUTRO_CHORDS = ['Dmaj7', 'E', ['D', 'Dm'], 'Aadd9']

SECTIONS = [
    # 旋律, 和弦, 力度, 伴奏型, 八度叠加, 移调
    (INTRO,       INTRO_CHORDS,     0.40, 'sparse', False, 0),
    (VERSE,       VERSE_CHORDS,     0.52, 'arp8',   False, 0),
    (HOOK_CHORUS, CHORUS_CHORDS,    0.72, 'arp8',   False, 0),
    (INTERLUDE,   INTERLUDE_CHORDS, 0.50, 'arp8',   False, 0),
    (BRIDGE,      BRIDGE_CHORDS,    0.66, 'arp16',  False, 0),
    (HOOK_CHORUS, CHORUS_CHORDS,    0.88, 'arp16',  True,  2),
    (OUTRO,       OUTRO_CHORDS,     0.55, 'arp8',   False, 2),
]

# ---------- 生成音符事件 ----------
events = []   # (起始拍, 时值拍, midi, 力度, 是否旋律)
beat = 0.0
for mel, chords, dyn, pattern, octave, tr in SECTIONS:
    for bar, chord in zip(mel, chords):
        t = beat
        for p, d in bar:
            if p is not None:
                accent = 1.1 if d >= 1.5 else 1.0
                v = min(dyn * accent * (0.9 + 0.12 * rng.random()), 1.0)
                events.append((t, d + 0.35, n(p) + tr, v, True))
                if octave:
                    events.append((t, d + 0.35, n(p) + tr - 12, v * 0.5, True))
            t += d
        halves = chord if isinstance(chord, list) else [chord]
        span = 4 / len(halves)
        for h, sym in enumerate(halves):
            bass, (five, col, ten, top) = chord_tones(sym)
            b0 = beat + span * h
            end = b0 + span
            if pattern == 'sparse':
                seq, step = [bass, five, col, ten], 1.0
            elif pattern == 'arp16':
                seq, step = [bass, five, col, ten, top, ten, col, five], 0.25
            else:
                seq, step = [bass, five, col, ten, top, ten, col, five], 0.5
            count = int(span / step)
            for k in range(count):
                m = seq[k % len(seq)]
                if k > 0 and k % len(seq) == 0:
                    m = five           # 16 分音型第二轮不再重复根音
                s = b0 + k * step
                acc = 1.0 if k == 0 else 0.72
                v = dyn * 0.5 * acc * (0.85 + 0.2 * rng.random())
                events.append((s, end - s + 0.25, m + tr, v, False))
        beat += 4

TOTAL_BEATS = beat


def beat_to_sec(b):
    """最后三小节渐慢到 60% 速度"""
    rit = TOTAL_BEATS - 12
    if b <= rit:
        return b * BEAT
    x = min(b - rit, 12)
    k = 0.4 / 12
    extra = max(b - rit - 12, 0) / 0.6
    return rit * BEAT + BEAT * (np.log(1 / (1 - k * x)) / k + extra)


def write_midi(path):
    mid = mido.MidiFile(ticks_per_beat=480)
    trk = mido.MidiTrack()
    mid.tracks.append(trk)
    trk.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM)))
    trk.append(mido.MetaMessage('track_name', name='The Shape of Missing You'))
    trk.append(mido.Message('program_change', program=0))
    msgs = []
    for s, d, m, v, _ in events:
        msgs.append((int(s * 480), 1, m, int(20 + 100 * v)))
        msgs.append((int((s + d) * 480), 0, m, 0))
    msgs.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, on, m, vel in msgs:
        trk.append(mido.Message('note_on' if on else 'note_off', note=m,
                                velocity=vel, time=tick - last))
        last = tick
    mid.save(path)


# ---------- 钢琴音色合成（与第一版相同）----------
def piano_note(midi, vel, dur):
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    length = dur + 1.8 + 1.5 * max(0, 1 - (midi - 30) / 70)
    N = int(length * SR)
    t = np.arange(N) / SR
    B_inh = 0.0004 * (f0 / 261.6) ** 0.5
    base_decay = 0.9 + 3.5 * max(midi - 30, 0) / 60
    sig = np.zeros(N)
    bright = 0.5 + 0.5 * vel
    for k in range(1, 13):
        fk = k * f0 * np.sqrt(1 + B_inh * k * k)
        if fk > SR / 2.2:
            break
        amp = (1.0 / k ** (1.6 - 0.6 * bright)) * (1 if k < 7 else 0.5)
        dec = base_decay * (1 + 0.35 * (k - 1))
        env = 0.7 * np.exp(-t * dec) + 0.3 * np.exp(-t * dec * 0.25)
        detune = 1 + 0.0007 * (rng.random() - 0.5)
        ph = rng.random() * 2 * np.pi
        sig += amp * env * (np.sin(2 * np.pi * fk * t + ph)
                            + 0.6 * np.sin(2 * np.pi * fk * detune * t + ph))
    atk = np.minimum(t / 0.004, 1.0)
    hammer = rng.standard_normal(N) * np.exp(-t * 90) * 0.015 * vel
    sig = sig * atk + hammer
    rel = np.ones(N)
    r0 = int(dur * SR)
    if r0 < N:
        rel[r0:] = np.exp(-(t[r0:] - dur) * 6)
    return sig * rel * vel ** 1.3


def render(path):
    total_sec = beat_to_sec(TOTAL_BEATS) + 6
    L = np.zeros(int(total_sec * SR))
    R = np.zeros_like(L)
    for s, d, m, v, is_mel in events:
        # 旋律略微抢拍一点点，更有"人在弹"的感觉
        start = beat_to_sec(s) + rng.normal(-0.006 if is_mel else 0.004, 0.006)
        start = max(start, 0)
        dur = beat_to_sec(s + d) - beat_to_sec(s)
        x = piano_note(m, v * (1.25 if is_mel else 1.0), dur)
        i0 = int(start * SR)
        x = x[:len(L) - i0]
        pan = np.clip((m - 40) / 60, 0, 1)
        L[i0:i0 + len(x)] += x * np.cos(pan * np.pi / 2 * 0.6 + 0.2)
        R[i0:i0 + len(x)] += x * np.sin(pan * np.pi / 2 * 0.6 + 0.4)
    irl = int(2.8 * SR)
    ti = np.arange(irl) / SR
    ir_l = rng.standard_normal(irl) * np.exp(-ti * 2.4)
    ir_r = rng.standard_normal(irl) * np.exp(-ti * 2.4)
    ir_l[:int(0.02 * SR)] = 0
    ir_r[:int(0.027 * SR)] = 0
    wet_l = fftconvolve(L, ir_l)[:len(L)]
    wet_r = fftconvolve(R, ir_r)[:len(R)]
    wet_l *= np.max(np.abs(L)) / np.max(np.abs(wet_l))
    wet_r *= np.max(np.abs(R)) / np.max(np.abs(wet_r))
    L = L + 0.3 * wet_l
    R = R + 0.3 * wet_r
    stereo = np.stack([L, R], axis=1)
    stereo = np.tanh(stereo / np.max(np.abs(stereo)) * 1.1) * 0.89
    fade = int(4 * SR)
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    pcm = (stereo * 32767).astype(np.int16)
    enc = lameenc.Encoder()
    enc.set_bit_rate(192)
    enc.set_in_sample_rate(SR)
    enc.set_channels(2)
    enc.set_quality(2)
    with open(path, 'wb') as f:
        f.write(enc.encode(pcm.tobytes()) + enc.flush())
    return total_sec


if __name__ == '__main__':
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for mel, chords, *_ in SECTIONS:
        for bar in mel:
            assert abs(sum(d for _, d in bar) - 4) < 1e-9, bar
        assert len(mel) == len(chords)
    write_midi(os.path.join(here, 'shape_of_missing_you.mid'))
    sec = render(os.path.join(here, 'shape_of_missing_you.mp3'))
    print(f'done: {len(events)} notes, {sec:.1f}s')
