"""
《雨后的信》(Letter After the Rain) —— 原创钢琴小品
风格参考：温柔、抒情、旋律朗朗上口的韩式钢琴曲（类似 Kiss the Rain 的气质）

结构：前奏(4) - A(8) - A'(8) - B(8) - A''(8, 高八度) - 尾声(4)
调性：降E大调，4/4，约 72 BPM
和声：卡农式下行低音 Eb - Bb/D - Cm - Gm/Bb - Ab - Eb/G - Fm - Bb

输出：letter_after_the_rain.mid / letter_after_the_rain.mp3
依赖：numpy scipy mido lameenc
"""
import numpy as np
import mido
import lameenc
from scipy.signal import fftconvolve

SR = 44100
BPM = 72
BEAT = 60.0 / BPM
rng = np.random.default_rng(7)

# ---------- 音名 ----------
NAMES = {'C': 0, 'Db': 1, 'D': 2, 'Eb': 3, 'E': 4, 'F': 5, 'Gb': 6,
         'G': 7, 'Ab': 8, 'A': 9, 'Bb': 10, 'B': 11}


def n(name):
    """'Eb5' -> MIDI 编号"""
    pitch, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + NAMES[pitch]


# ---------- 和弦（低音, 和弦音）----------
CHORDS = {
    'Eb':    ('Eb2', ['Eb3', 'Bb3', 'G4']),
    'Bb/D':  ('D2',  ['Bb2', 'F3', 'D4']),
    'Cm':    ('C2',  ['C3', 'G3', 'Eb4']),
    'Gm/Bb': ('Bb1', ['G2', 'D3', 'Bb3']),
    'Ab':    ('Ab1', ['Ab2', 'Eb3', 'C4']),
    'Eb/G':  ('G1',  ['Eb3', 'Bb3', 'G4']),
    'Fm':    ('F1',  ['F2', 'C3', 'Ab3']),
    'Bb':    ('Bb1', ['Bb2', 'F3', 'D4']),
    'Bb7':   ('Bb1', ['Ab2', 'F3', 'D4']),
    'Gm':    ('G1',  ['G2', 'D3', 'Bb3']),
    'Fm7':   ('F1',  ['Eb3', 'C3', 'Ab3']),
    'Absus': ('Ab1', ['Bb2', 'Eb3', 'C4']),
}

CANON = ['Eb', 'Bb/D', 'Cm', 'Gm/Bb', 'Ab', 'Eb/G', 'Fm', 'Bb']

# ---------- 旋律 (音名, 拍数)；None 表示休止 ----------
A = [
    [('Bb4', .5), ('Eb5', .5), ('G5', 2), ('F5', .5), ('Eb5', .5)],
    [('F5', 1.5), ('D5', .5), ('Bb4', 2)],
    [('C5', .5), ('Eb5', .5), ('G5', 2), ('F5', .5), ('Eb5', .5)],
    [('D5', 2), ('Eb5', .5), ('F5', 1.5)],
    [('Ab5', 1.5), ('G5', .5), ('F5', .5), ('Eb5', .5), ('C5', 1)],
    [('Bb4', .5), ('Eb5', .5), ('G5', 2), ('Eb5', 1)],
    [('F5', .5), ('G5', .5), ('Ab5', 1.5), ('G5', .5), ('F5', 1)],
    [('G5', 1), ('F5', 1), ('D5', 2)],
]
# A'：前六小节相同，结尾回到主音
A2 = A[:6] + [
    [('F5', 1), ('G5', .5), ('Ab5', .5), ('G5', 1), ('F5', 1)],
    [('Eb5', 4)],
]
A2_CHORDS = CANON[:6] + [['Fm7', 'Bb7'], 'Eb']

B = [
    [('C6', 1.5), ('Bb5', .5), ('Ab5', 1), ('Eb5', 1)],
    [('Bb5', 1.5), ('Ab5', .5), ('G5', 1), ('F5', 1)],
    [('G5', 1), ('Bb5', 1), ('D6', 1.5), ('C6', .5)],
    [('C6', 2), ('G5', 1), ('Eb5', 1)],
    [('Ab5', .5), ('Bb5', .5), ('C6', 1), ('Eb6', 1.5), ('D6', .5)],
    [('D6', 1), ('C6', .5), ('Bb5', .5), ('F5', 2)],
    [('G5', .5), ('Ab5', .5), ('Bb5', 1), ('Eb6', 1.5), ('D6', .5)],
    [('C6', 1), ('Bb5', 1), ('Ab5', .5), ('G5', .5), ('F5', 1)],
]
B_CHORDS = ['Ab', 'Bb', 'Gm', 'Cm', 'Fm', 'Bb', 'Eb/G', ['Ab', 'Bb7']]

INTRO_CHORDS = ['Eb', 'Bb/D', 'Cm', ['Absus', 'Bb']]
INTRO_MEL = [
    [(None, 2), ('G5', .5), ('Bb5', .5), ('Eb6', 1)],
    [('D6', 4)],
    [(None, 2), ('Eb6', .5), ('D6', .5), ('C6', 1)],
    [('Bb5', 4)],
]
OUTRO_CHORDS = ['Ab', ['Fm7', 'Bb7'], 'Eb', 'Eb']
OUTRO_MEL = [
    [('C6', 1.5), ('Bb5', .5), ('Ab5', 1), ('G5', 1)],
    [('F5', 1), ('G5', .5), ('Ab5', .5), ('G5', 1), ('F5', 1)],
    [('Eb5', 2), ('Bb4', 1), ('G5', 1)],
    [('Eb6', 4)],
]


def up_octave(section):
    return [[(None if p is None else p[:-1] + str(int(p[-1]) + 1), d)
             for p, d in bar] for bar in section]


SECTIONS = [
    # (旋律, 和弦, 力度, 伴奏型, 旋律八度叠加)
    (INTRO_MEL, INTRO_CHORDS, 0.45, 'arp8', False),
    (A,  CANON,     0.60, 'arp8', False),
    (A2, A2_CHORDS, 0.65, 'arp8', False),
    (B,  B_CHORDS,  0.78, 'arp16', False),
    (A2, A2_CHORDS, 0.85, 'arp16', True),
    (OUTRO_MEL, OUTRO_CHORDS, 0.55, 'arp8', False),
]

# ---------- 生成音符事件 (起始拍, 时值拍, midi, 力度, 是否旋律) ----------
events = []
beat = 0.0
for mel, chords, dyn, pattern, octave in SECTIONS:
    for bar_i, (bar, chord) in enumerate(zip(mel, chords)):
        # 旋律
        t = beat
        for p, d in bar:
            if p is not None:
                v = dyn * (0.9 + 0.12 * rng.random()) * (1.08 if d >= 1.5 else 1.0)
                events.append((t, d + 0.4, n(p), min(v, 1.0), True))
                if octave:
                    events.append((t, d + 0.4, n(p) - 12, v * 0.55, True))
            t += d
        # 伴奏：分解和弦，延音踏板效果（音符保持到半小节/小节结束）
        halves = chord if isinstance(chord, list) else [chord, chord]
        for h, name in enumerate(halves):
            bass, tones = CHORDS[name]
            b0 = beat + 2 * h
            end = b0 + 2
            if h == 0 and not isinstance(chord, list):
                end = beat + 4
            seq = [n(bass), n(tones[1]), n(tones[2]), n(tones[1]) + 12]
            if pattern == 'arp16':
                seq = [n(bass), n(tones[1]), n(tones[2]), n(tones[1]) + 12,
                       n(tones[2]) + 12, n(tones[1]) + 12, n(tones[2]), n(tones[1])]
                step = 0.25
            else:
                step = 0.5
            if h == 1 and pattern == 'arp8' and not isinstance(chord, list):
                # 后半小节换成回落的音型，让左手像水波一样起伏
                seq = [n(tones[0]) + 12, n(tones[2]), n(tones[1]), n(tones[2]) - 12]
            for k, m in enumerate(seq):
                s = b0 + k * step
                acc = 1.0 if k == 0 else 0.75
                v = dyn * 0.55 * acc * (0.85 + 0.2 * rng.random())
                events.append((s, end - s + 0.3, m, v, False))
        beat += 4

TOTAL_BEATS = beat


# ---------- 渐慢（最后 3 小节）----------
def beat_to_sec(b):
    rit_start = TOTAL_BEATS - 12
    if b <= rit_start:
        return b * BEAT
    x = b - rit_start
    # 速度线性降到 60%
    k = 0.4 / 12
    return rit_start * BEAT + BEAT * (np.log(1 / (1 - k * x)) / k if x < 12 else np.log(1 / 0.6) / k)


# ---------- 写 MIDI ----------
def write_midi(path):
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM)))
    tr.append(mido.MetaMessage('track_name', name='Letter After the Rain'))
    tr.append(mido.Message('program_change', program=0))
    msgs = []
    for s, d, m, v, _ in events:
        msgs.append((int(s * 480), 1, m, int(20 + 100 * v)))
        msgs.append((int((s + d) * 480), 0, m, 0))
    msgs.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, on, m, vel in msgs:
        tr.append(mido.Message('note_on' if on else 'note_off', note=m,
                               velocity=vel, time=tick - last))
        last = tick
    mid.save(path)


# ---------- 钢琴音色合成 ----------
def piano_note(midi, vel, dur):
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    length = dur + 1.8 + 1.5 * (1 - (midi - 30) / 70)
    N = int(length * SR)
    t = np.arange(N) / SR
    B_inh = 0.0004 * (f0 / 261.6) ** 0.5          # 弦的非谐性
    base_decay = 0.9 + 3.5 * (midi - 30) / 60      # 高音衰减更快
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
    # 击弦瞬态
    atk = np.minimum(t / 0.004, 1.0)
    hammer = rng.standard_normal(N) * np.exp(-t * 90) * 0.015 * vel
    sig = sig * atk + hammer
    # 松开琴键后的阻尼
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
        jitter = rng.normal(0, 0.008)
        start = beat_to_sec(s) + max(jitter, -0.01)
        dur = beat_to_sec(s + d) - beat_to_sec(s)
        x = piano_note(m, v * (1.15 if is_mel else 1.0), dur)
        i0 = int(start * SR)
        x = x[:len(L) - i0]
        pan = np.clip((m - 40) / 60, 0, 1)              # 低音偏左，高音偏右
        L[i0:i0 + len(x)] += x * np.cos(pan * np.pi / 2 * 0.6 + 0.2)
        R[i0:i0 + len(x)] += x * np.sin(pan * np.pi / 2 * 0.6 + 0.4)
    # 简单混响：指数衰减噪声脉冲响应
    irl = int(2.6 * SR)
    ti = np.arange(irl) / SR
    ir_l = rng.standard_normal(irl) * np.exp(-ti * 2.6)
    ir_r = rng.standard_normal(irl) * np.exp(-ti * 2.6)
    ir_l[:int(0.02 * SR)] = 0
    ir_r[:int(0.027 * SR)] = 0
    wet_l = fftconvolve(L, ir_l)[:len(L)]
    wet_r = fftconvolve(R, ir_r)[:len(R)]
    wet_l *= np.max(np.abs(L)) / np.max(np.abs(wet_l))
    wet_r *= np.max(np.abs(R)) / np.max(np.abs(wet_r))
    L = L + 0.28 * wet_l
    R = R + 0.28 * wet_r
    stereo = np.stack([L, R], axis=1)
    stereo = np.tanh(stereo / np.max(np.abs(stereo)) * 1.1) * 0.89
    # 淡出
    fade = int(4 * SR)
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    pcm = (stereo * 32767).astype(np.int16)
    enc = lameenc.Encoder()
    enc.set_bit_rate(192)
    enc.set_in_sample_rate(SR)
    enc.set_channels(2)
    enc.set_quality(2)
    data = enc.encode(pcm.tobytes()) + enc.flush()
    with open(path, 'wb') as f:
        f.write(data)
    return total_sec


if __name__ == '__main__':
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    write_midi(os.path.join(here, 'letter_after_the_rain.mid'))
    sec = render(os.path.join(here, 'letter_after_the_rain.mp3'))
    print(f'done: {len(events)} notes, {sec:.1f}s')
