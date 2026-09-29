"""
用真实钢琴采样（Salamander Grand Piano，Yamaha C5，CC-BY 3.0）渲染乐谱 JSON

    python3 render_salamander.py score.json out.mp3 --samples <采样目录>

采样来自 "Accurate Salamander Grand Piano V6.2"（Alexander Holm 录制，CC-BY 3.0），
文件名形如 060_C4v08.wav：每小三度一个采样，v01..v16 为力度层。
这里只用到偶数层 v02..v12（弱奏到中强），足够覆盖温柔的曲子。

演奏模拟：
  - 延音踏板：每次换和弦时换踏板，音符一直响到下一次抬踏板
  - 力度层选择决定音色（弱奏更柔和），响度由力度曲线单独控制
  - 乐句呼吸：每 4 小节乐句末尾微微放慢；结尾渐慢
  - 旋律略微领先伴奏几毫秒，时值与力度有细微随机
  - 频率相关衰减的立体声混响
"""
import json
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_tools import arrange, validate  # noqa: E402

SR = 48000
SAMPLE_NOTES = list(range(24, 103, 3))          # C1 .. F#7
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
LAYERS = [2, 4, 6, 8, 10, 12]
rng = np.random.default_rng(2026)
_cache = {}


def sample_file(root, note, layer):
    name = f'{note:03d}_{NAMES[note % 12]}{note // 12 - 1}v{layer:02d}.wav'
    return os.path.join(root, name)


def load(root, note, layer):
    key = (note, layer)
    if key not in _cache:
        sr, x = wavfile.read(sample_file(root, note, layer))
        x = x.astype(np.float32) / 2 ** 31
        _cache[key] = (sr, x)
    return _cache[key]


def voice_note(root, midi, midi_vel, length_sec):
    s = min(SAMPLE_NOTES, key=lambda k: abs(k - midi))
    layer_f = midi_vel / 127 * 16
    layer = min(LAYERS, key=lambda L: abs(L - layer_f))
    sr, x = load(root, s, layer)
    ratio = sr / SR * 2 ** ((midi - s) / 12)
    n_out = min(int(length_sec * SR), int((len(x) - 2) / ratio))
    pos = np.arange(n_out) * ratio
    i = pos.astype(np.int64)
    frac = (pos - i)[:, None].astype(np.float32)
    y = x[i] * (1 - frac) + x[i + 1] * frac
    return y


def tempo_map(score, total_beats):
    """每拍的时长（秒），包含乐句呼吸与结尾渐慢"""
    base = 60.0 / score['bpm']
    n = int(np.ceil(total_beats)) + 16
    mult = np.ones(n)
    for b in range(n):
        pos_in_phrase = b % 16
        if pos_in_phrase == 15:
            mult[b] *= 1.07
        elif pos_in_phrase == 14:
            mult[b] *= 1.03
    rit = score.get('ending', {}).get('ritardando_bars', 3) * 4
    start = int(total_beats - rit)
    for b in range(start, n):
        x = min((b - start + 1) / max(rit, 1), 1.0)
        mult[b] *= 1 + 0.7 * x ** 1.5
    edges = np.concatenate([[0], np.cumsum(base * mult)])
    return lambda beat: float(np.interp(beat, np.arange(len(edges)), edges))


def pedal_changes(score):
    """每个和弦开始的拍位 = 换踏板的位置"""
    out, beat = [], 0.0
    for sec in score['sections']:
        for bar in sec['bars']:
            span = 4 / len(bar['chords'])
            for h in range(len(bar['chords'])):
                out.append(beat + span * h)
            beat += 4
    out.append(beat + 8)
    return np.array(out)


def reverb_ir(seconds=3.2, rt_low=2.6, rt_high=1.1):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    irs = []
    for ch in range(2):
        noise = rng.standard_normal(n)
        low = sosfilt(butter(2, 1800, 'low', fs=SR, output='sos'), noise)
        high = noise - low
        ir = low * np.exp(-6.9 * t / rt_low) + 0.6 * high * np.exp(-6.9 * t / rt_high)
        pre = int((0.018 + 0.006 * ch) * SR)
        ir[:pre] = 0
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    return irs


def render(score, out_path, sample_root, wet=0.24):
    events, total_beats = arrange(score)
    b2s = tempo_map(score, total_beats)
    pedals = pedal_changes(score)
    end_sec = b2s(total_beats) + 7
    mix = np.zeros((int(end_sec * SR), 2), np.float32)
    for e in events:
        midi_vel = int(np.clip(20 + 90 * e['vel'] * (0.94 + 0.12 * rng.random()), 8, 120))
        lead = -0.012 if e['voice'] == 'melody' else 0.0
        t0 = max(b2s(e['start']) + lead + rng.normal(0, 0.006), 0)
        note_end_beat = e['start'] + e['dur']
        # 踏板在音符结束后的第一次换踏板时抬起
        k = np.searchsorted(pedals, note_end_beat - 1e-6)
        release_beat = pedals[min(k, len(pedals) - 1)]
        t_rel = b2s(release_beat) + 0.05
        hold = max(t_rel - t0, 0.12)
        fade = 0.35 if e['midi'] < 60 else 0.22
        y = voice_note(sample_root, e['midi'], midi_vel, hold + fade)
        n_hold = int(hold * SR)
        if len(y) > n_hold:
            env = np.ones(len(y), np.float32)
            nf = len(y) - n_hold
            env[n_hold:] = np.exp(-np.arange(nf) / (fade * SR / 5)).astype(np.float32)
            y = y * env[:, None]
        gain = (midi_vel / 127) ** 1.8
        i0 = int(t0 * SR)
        y = y[:len(mix) - i0]
        mix[i0:i0 + len(y)] += y * gain
    # 温暖：轻微削减 7kHz 以上
    sos = butter(1, 7000, 'low', fs=SR, output='sos')
    warm = sosfilt(sos, mix, axis=0)
    mix = 0.55 * mix + 0.45 * warm
    irs = reverb_ir()
    wet_sig = np.stack([fftconvolve(mix[:, c], irs[c])[:len(mix)] for c in range(2)], axis=1)
    out = mix + wet * wet_sig * 2.2
    peak = np.max(np.abs(out))
    out = out / peak * 0.93
    out = np.tanh(out * 1.05) / np.tanh(1.05) * 0.93
    fade = int(5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
    # 去掉末尾过长的静音
    pcm = (out * 32767).astype(np.int16)
    if out_path.endswith('.wav'):
        wavfile.write(out_path, SR, pcm)
    else:
        import lameenc
        enc = lameenc.Encoder()
        enc.set_bit_rate(256)
        enc.set_in_sample_rate(SR)
        enc.set_channels(2)
        enc.set_quality(2)
        with open(out_path, 'wb') as f:
            f.write(enc.encode(pcm.tobytes()) + enc.flush())
    return len(pcm) / SR


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    root = sys.argv[sys.argv.index('--samples') + 1]
    with open(src) as f:
        score = json.load(f)
    errs = validate(score)
    if errs:
        sys.exit('\n'.join(errs))
    sec = render(score, dst, root)
    print(f'rendered {dst}: {sec:.1f}s')
