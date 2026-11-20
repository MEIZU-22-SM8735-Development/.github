#!/usr/bin/env python3
"""Nested treemap of the Meizu 22 mainline adaptation progress.

Reads the STAGES table below and writes profile/assets/progress-dark.{svg,png}
(two times the nominal size, for crisp rendering on GitHub).

    python3 tools/progress/gen_tree.py              # into ../../profile/assets
    python3 tools/progress/gen_tree.py /tmp/out     # somewhere else

Needs rsvg-convert (librsvg) on PATH.
"""
import os
import sys
import math
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_OUT = os.path.join(REPO, "profile", "assets")

D, U, W, B, T = "done", "wait", "wait", "blocked", "todo"

STAGES = [
    ("P1", "Boot · Bus · Storage", [
        ("P1-01", "Boot & SoC ID", D, None),
        ("P1-02", "earlycon / pstore", D, None),
        ("P1-03", "SimpleFB Framebuffer", D, None),
        ("P1-04", "GCC / TCSRCC Clocks", D, None),
        ("P1-05", "RPMh Power Domains", D, None),
        ("P1-06", "PMIC Complex", None, [("PMK8550", D), ("PMIH010X", D), ("PM8550VE", D),
                                        ("PM8550VS", D), ("PMXR2230", D)]),
        ("P1-07", "TLMM Pinmux", D, None),
        ("P1-08", "Interconnect / LLCC", D, None),
        ("P1-09", "SMMU / IOMMU", D, None),
        ("P1-10", "LPDDR5X Memory Map", D, None),
        ("P1-11", "UFS 4.0", None, [("Controller", D), ("PHY", D), ("Low Power", D)]),
        ("P1-12", "USB Gadget / xHCI", D, None),
        ("P1-13", "GENI I2C Buses", D, None),
    ]),
    ("P2", "CPU · DVFS · Thermal", [
        ("P2-01", "SMP 8-Core Boot", D, None),
        ("P2-02", "DVFS 4 Clusters", None, [("X4 3.2G", D), ("A720 3.0G", D),
                                            ("A720 2.8G", D), ("A720 2.0G", D)]),
        ("P2-03", "EAS Scheduler", T, None),
        ("P2-04", "CPUIdle Light Sleep", T, None),
        ("P2-05", "s2idle Deep Sleep", T, None),
        ("P2-06", "TSENS Sensors", None, [("8-zone", D), ("11-zone", D),
                                          ("15-zone", D), ("5-zone", D)]),
        ("P2-07", "Board NTC", D, None),
        ("P2-08", "Thermal Trips", None, [("CPU", D), ("GPU", D), ("PMIC", D)]),
    ]),
    ("P3", "Display · Touch · Type-C", [
        ("P3-01", "DPU / DSI", None, [("DPU", D), ("DSI", D), ("PHY", D)]),
        ("P3-02", "C9 LTPO Panel", D, None),
        ("P3-03", "Backlight / HBM", D, None),
        ("P3-04", "ADFR Adaptive Refresh", D, None),
        ("P3-05", "Capacitive Touch", D, None),
        ("P3-06", "Type-C Role Switch", D, None),
        ("P3-07", "USB 3.2 PHY", D, None),
        ("P3-08", "DP Alt Mode", D, None),
    ]),
    ("P4", "GPU · Video Codec", [
        ("P4-01", "GPU Clock / GMU", D, None),
        ("P4-02", "Adreno 825", None, [("catalog", D), ("descriptors", D)]),
        ("P4-03", "devfreq / Recovery", D, None),
        ("P4-04", "Mesa / Turnip", D, None),
        ("P4-05", "Iris Decode", T, None),
    ]),
    ("P5", "Wireless · Modem · GNSS", [
        ("P5-01", "PCIe Controller", D, None),
        ("P5-02", "Wi-Fi 7 / ath12k", None, [("2.4G", D), ("5G", D), ("BDF", D)]),
        ("P5-03", "Bluetooth 5.4", D, None),
        ("P5-04", "Q6V5 / ADSP / MPSS", W, None),
        ("P5-05", "QRTR / IPA / 5G", T, None),
        ("P5-06", "VoLTE / IMS", T, None),
        ("P5-07", "GNSS", T, None),
        ("P5-08", "NFC", T, None),
        ("P5-09", "UWB", T, None),
        ("P5-10", "IR Remote", T, None),
    ]),
    ("P6", "Power · Audio · Sensors", [
        ("P6-01", "Fuel Gauge", D, None),
        ("P6-02", "PD / PPS Charging", W, None),
        ("P6-03", "80W Fast Charge", T, None),
        ("P6-04", "Wireless Charging", T, None),
        ("P6-05", "AudioReach Audio", U, None),
        ("P6-06", "Stereo Speakers", None, [("Top", T), ("Bottom", T)]),
        ("P6-07", "Mics / UCM", T, None),
        ("P6-08", "Haptic Motor", T, None),
        ("P6-09", "Aicy LED", T, None),
        ("P6-10", "Sensors", T, None),
    ]),
    ("P7", "Closed Blobs", [
        ("P7-01", "CAMSS / CCI", T, None),
        ("P7-02", "Quad Camera", None, [("OV50H", T), ("OV50D", T), ("IMX882", T), ("Front", T)]),
        ("P7-03", "libcamera Pipeline", T, None),
        ("P7-04", "Ultrasonic Fingerprint", T, None),
        ("P7-05", "NPU / FastRPC", T, None),
    ]),
]

FILL = {"done": "#3fb950", "wait": "#d29922", "blocked": "#da3633", "todo": "#414952"}
INK = {"done": "#06210f", "wait": "#1f1503", "blocked": "#ffffff", "todo": "#c9d1d9"}
BG, HEAD = "#0b0d10", "#0b0d10"
BORDER = "#20262e"
STAGE_BG = "#111720"
FONT = "MiSans, Noto Sans CJK SC, sans-serif"

W, H = 1000, 780
M = 12
STAGE_HEAD = 20
ITEM_HEAD = 16
GAP = 0


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


WIDTH = {}


def _cw(c):
    """Approximate advance width in em (MiSans / Noto Sans CJK metrics)."""
    o = ord(c)
    if o > 0x2E80:
        return 1.0
    if c in WIDTH:
        return WIDTH[c]
    if c.isupper():
        return 0.68
    if c.isdigit():
        return 0.60
    if c.islower():
        return 0.55
    if c == " ":
        return 0.30
    return 0.42


def tw(s, size):
    return sum(size * _cw(c) for c in s)


def worst(row, length):
    s = sum(row)
    if s <= 0:
        return float("inf")
    return max(length * length * max(row) / (s * s), s * s / (length * length * min(row)))


def squarify(values, x, y, w, h):
    vals = list(values)
    total = sum(vals)
    if total <= 0:
        return []
    vals = [v * w * h / total for v in vals]
    rects = []
    while vals:
        row = [vals.pop(0)]
        while vals and worst(row + [vals[0]], min(w, h)) <= worst(row, min(w, h)):
            row.append(vals.pop(0))
        s = sum(row)
        if w >= h:
            rw = s / h if h else 0
            yy = y
            for v in row:
                rh = v * h / s
                rects.append((x, yy, rw, rh))
                yy += rh
            x += rw
            w -= rw
        else:
            rh = s / w if w else 0
            xx = x
            for v in row:
                rw = v * w / s
                rects.append((xx, y, rw, rh))
                xx += rw
            y += rh
            h -= rh
    return rects


TOKEN = re.compile(r"[\u4e00-\u9fff]+[\uff0c\u3002\u3001\u00b7]?|[A-Za-z0-9][A-Za-z0-9./+-]*|\s+|[^\s]")


def _hard_break(tok, width, fs):
    parts, cur = [], ""
    for ch in tok:
        if cur and tw(cur + ch, fs) > width:
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def wrap(text, width, fs):
    lines, cur = [], ""
    for tok in TOKEN.findall(text):
        if tok.isspace():
            if cur and not cur.endswith(" "):
                cur += " "
            continue
        cand = cur + tok
        if tw(cand, fs) <= width:
            cur = cand
            continue
        if cur.strip():
            lines.append(cur.strip())
        if tw(tok, fs) > width:
            parts = _hard_break(tok, width, fs)
            lines.extend(parts[:-1])
            cur = parts[-1]
        else:
            cur = tok
    if cur.strip():
        lines.append(cur.strip())
    return lines


CLIPS = []


def clip_rect(x, y, w, h):
    cid = f"cp{len(CLIPS)}"
    CLIPS.append((cid, x, y, w, h))
    return cid


def label(x, y, w, h, text, fs, ink, pad=4, weight=600, center=False):
    maxw = w - 2 * pad - 2
    maxh = h - 2 * pad - 1
    if maxw < 12 or maxh < fs:
        return ""
    lines = wrap(text, maxw, fs)
    fixed = []
    for ln in lines:
        if tw(ln, fs) > maxw:
            cut = ln
            while cut and tw(cut + "…", fs) > maxw:
                cut = cut[:-1]
            ln = (cut + "…") if cut else ln[0]
        fixed.append(ln)
    lines = fixed
    lh = fs * 1.18
    keep = max(1, int(maxh // lh))
    if len(lines) > keep:
        lines = lines[:keep]
        last = lines[-1]
        while tw(last + "…", fs) > maxw and len(last) > 1:
            last = last[:-1]
        lines[-1] = last + "…"
    cid = clip_rect(x, y, w, h)
    out = [f'<g clip-path="url(#{cid})">']
    total = lh * len(lines)
    ty = y + pad + (h - 2 * pad - total) / 2 + fs if center else y + pad + fs
    for i, ln in enumerate(lines):
        if center:
            out.append(f'<text x="{x + w / 2:.1f}" y="{ty + i * lh:.1f}" text-anchor="middle" '
                       f'font-family="{FONT}" font-size="{fs}" font-weight="{weight}" '
                       f'fill="{ink}">{esc(ln)}</text>')
        else:
            out.append(f'<text x="{x + pad}" y="{ty + i * lh:.1f}" '
                       f'font-family="{FONT}" font-size="{fs}" font-weight="{weight}" '
                       f'fill="{ink}">{esc(ln)}</text>')
    out.append("</g>")
    return "".join(out)


def fit_fs(text, w, h, pad):
    """Largest size (8-12.8) at which `text` fits the box in <=3 lines."""
    maxw = w - 2 * pad - 2
    maxh = h - 2 * pad - 1
    if maxw <= 0 or maxh <= 0:
        return 8.0
    unit = tw(text, 1)
    words = [t for t in TOKEN.findall(text) if not t.isspace()]
    widest = max(tw(t, 1) for t in words) if words else unit
    best = 8.0
    for n in (1, 2, 3):
        fs = min(maxw * n / unit, maxh / (n * 1.18))
        if fs >= 8.0:
            best = max(best, min(fs, 12.4))
    # never break a word in half: cap by the widest single token
    return round(max(6.5, min(best, maxw / widest) * 0.97), 1)


def leaves(item):
    return 1 if item[3] is None else len(item[3])


def leaf_demand(label):
    """Area a single label asks for = the box its text needs, at 10px."""
    return (tw(label, 10) + 12) * 26 / 950.0


def demand(item):
    _, title, _, subs = item
    if subs:
        return 0.55 + sum(leaf_demand(lbl) for lbl, _ in subs)
    return leaf_demand(title)


def item_state(item):
    _, _, st, subs = item
    if subs is None:
        return st
    states = [s for _, s in subs]
    if all(s == D for s in states):
        return D
    if any(s == B for s in states):
        return B
    if any(s in (U, W) for s in states):
        return U
    return T


def build():
    s = [f'<rect width="{W}" height="{H}" fill="{BG}"/>']
    n_all = sum(len(items) for _, _, items in STAGES)
    n_done = sum(1 for _, _, items in STAGES for it in items if item_state(it) == D)

    # header -----------------------------------------------------------
    s.append('<g transform="translate(10,17.3) scale(1.85)">'
             '<path fill="#c9d1d9" d="M12.504 0c-.155 0-.315.008-.48.021-4.226.333-3.105 4.807-3.17 6.298-.076 1.092-.3 1.953-1.05 3.02-.885 1.051-2.127 2.75-2.716 4.521-.278.832-.41 1.684-.287 2.489a.424.424 0 00-.11.135c-.26.268-.45.6-.663.839-.199.199-.485.267-.797.4-.313.136-.658.269-.864.68-.09.189-.136.394-.132.602 0 .199.027.4.055.536.058.399.116.728.04.97-.249.68-.28 1.145-.106 1.484.174.334.535.47.94.601.81.2 1.91.135 2.774.6.926.466 1.866.67 2.616.47.526-.116.97-.464 1.208-.946.587-.003 1.23-.269 2.26-.334.699-.058 1.574.267 2.577.2.025.134.063.198.114.333l.003.003c.391.778 1.113 1.132 1.884 1.071.771-.06 1.592-.536 2.257-1.306.631-.765 1.683-1.084 2.378-1.503.348-.199.629-.469.649-.853.023-.4-.2-.811-.714-1.376v-.097l-.003-.003c-.17-.2-.25-.535-.338-.926-.085-.401-.182-.786-.492-1.046h-.003c-.059-.054-.123-.067-.188-.135a.357.357 0 00-.19-.064c.431-1.278.264-2.55-.173-3.694-.533-1.41-1.465-2.638-2.175-3.483-.796-1.005-1.576-1.957-1.56-3.368.026-2.152.236-6.133-3.544-6.139zm.529 3.405h.013c.213 0 .396.062.584.198.19.135.33.332.438.533.105.259.158.459.166.724 0-.02.006-.04.006-.06v.105a.086.086 0 01-.004-.021l-.004-.024a1.807 1.807 0 01-.15.706.953.953 0 01-.213.335.71.71 0 00-.088-.042c-.104-.045-.198-.064-.284-.133a1.312 1.312 0 00-.22-.066c.05-.06.146-.133.183-.198.053-.128.082-.264.088-.402v-.02a1.21 1.21 0 00-.061-.4c-.045-.134-.101-.2-.183-.333-.084-.066-.167-.132-.267-.132h-.016c-.093 0-.176.03-.262.132a.8.8 0 00-.205.334 1.18 1.18 0 00-.09.4v.019c.002.089.008.179.02.267-.193-.067-.438-.135-.607-.202a1.635 1.635 0 01-.018-.2v-.02a1.772 1.772 0 01.15-.768c.082-.22.232-.406.43-.533a.985.985 0 01.594-.2zm-2.962.059h.036c.142 0 .27.048.399.135.146.129.264.288.344.465.09.199.14.4.153.667v.004c.007.134.006.2-.002.266v.08c-.03.007-.056.018-.083.024-.152.055-.274.135-.393.2.012-.09.013-.18.003-.267v-.015c-.012-.133-.04-.2-.082-.333a.613.613 0 00-.166-.267.248.248 0 00-.183-.064h-.021c-.071.006-.13.04-.186.132a.552.552 0 00-.12.27.944.944 0 00-.023.33v.015c.012.135.037.2.08.334.046.134.098.2.166.268.01.009.02.018.034.024-.07.057-.117.07-.176.136a.304.304 0 01-.131.068 2.62 2.62 0 01-.275-.402 1.772 1.772 0 01-.155-.667 1.759 1.759 0 01.08-.668 1.43 1.43 0 01.283-.535c.128-.133.26-.2.418-.2zm1.37 1.706c.332 0 .733.065 1.216.399.293.2.523.269 1.052.468h.003c.255.136.405.266.478.399v-.131a.571.571 0 01.016.47c-.123.31-.516.643-1.063.842v.002c-.268.135-.501.333-.775.465-.276.135-.588.292-1.012.267a1.139 1.139 0 01-.448-.067 3.566 3.566 0 01-.322-.198c-.195-.135-.363-.332-.612-.465v-.005h-.005c-.4-.246-.616-.512-.686-.71-.07-.268-.005-.47.193-.6.224-.135.38-.271.483-.336.104-.074.143-.102.176-.131h.002v-.003c.169-.202.436-.47.839-.601.139-.036.294-.065.466-.065zm2.8 2.142c.358 1.417 1.196 3.475 1.735 4.473.286.534.855 1.659 1.102 3.024.156-.005.33.018.513.064.646-1.671-.546-3.467-1.089-3.966-.22-.2-.232-.335-.123-.335.59.534 1.365 1.572 1.646 2.757.13.535.16 1.104.021 1.67.067.028.135.06.205.067 1.032.534 1.413.938 1.23 1.537v-.043c-.06-.003-.12 0-.18 0h-.016c.151-.467-.182-.825-1.065-1.224-.915-.4-1.646-.336-1.77.465-.008.043-.013.066-.018.135-.068.023-.139.053-.209.064-.43.268-.662.669-.793 1.187-.13.533-.17 1.156-.205 1.869v.003c-.02.334-.17.838-.319 1.35-1.5 1.072-3.58 1.538-5.348.334a2.645 2.645 0 00-.402-.533 1.45 1.45 0 00-.275-.333c.182 0 .338-.03.465-.067a.615.615 0 00.314-.334c.108-.267 0-.697-.345-1.163-.345-.467-.931-.995-1.788-1.521-.63-.4-.986-.87-1.15-1.396-.165-.534-.143-1.085-.015-1.645.245-1.07.873-2.11 1.274-2.763.107-.065.037.135-.408.974-.396.751-1.14 2.497-.122 3.854a8.123 8.123 0 01.647-2.876c.564-1.278 1.743-3.504 1.836-5.268.048.036.217.135.289.202.218.133.38.333.59.465.21.201.477.335.876.335.039.003.075.006.11.006.412 0 .73-.134.997-.268.29-.134.52-.334.74-.4h.005c.467-.135.835-.402 1.044-.7zm2.185 8.958c.037.6.343 1.245.882 1.377.588.134 1.434-.333 1.791-.765l.211-.01c.315-.007.577.01.847.268l.003.003c.208.199.305.53.391.876.085.4.154.78.409 1.066.486.527.645.906.636 1.14l.003-.007v.018l-.003-.012c-.015.262-.185.396-.498.595-.63.401-1.746.712-2.457 1.57-.618.737-1.37 1.14-2.036 1.191-.664.053-1.237-.2-1.574-.898l-.005-.003c-.21-.4-.12-1.025.056-1.69.176-.668.428-1.344.463-1.897.037-.714.076-1.335.195-1.814.12-.465.308-.797.641-.984l.045-.022zm-10.814.049h.01c.053 0 .105.005.157.014.376.055.706.333 1.023.752l.91 1.664.003.003c.243.533.754 1.064 1.189 1.637.434.598.77 1.131.729 1.57v.006c-.057.744-.48 1.148-1.125 1.294-.645.135-1.52.002-2.395-.464-.968-.536-2.118-.469-2.857-.602-.369-.066-.61-.2-.723-.4-.11-.2-.113-.602.123-1.23v-.004l.002-.003c.117-.334.03-.752-.027-1.118-.055-.401-.083-.71.043-.94.16-.334.396-.4.69-.533.294-.135.64-.202.915-.47h.002v-.002c.256-.268.445-.601.668-.838.19-.201.38-.336.663-.336zm7.159-9.074c-.435.201-.945.535-1.488.535-.542 0-.97-.267-1.28-.466-.154-.134-.28-.268-.373-.335-.164-.134-.144-.333-.074-.333.109.016.129.134.199.2.096.066.215.2.36.333.292.2.68.467 1.167.467.485 0 1.053-.267 1.398-.466.195-.135.445-.334.648-.467.156-.136.149-.267.279-.267.128.016.034.134-.147.332a8.097 8.097 0 01-.69.468zm-1.082-1.583V5.64c-.006-.02.013-.042.029-.05.074-.043.18-.027.26.004.063 0 .16.067.15.135-.006.049-.085.066-.135.066-.055 0-.092-.043-.141-.068-.052-.018-.146-.008-.163-.065zm-.551 0c-.02.058-.113.049-.166.066-.047.025-.086.068-.14.068-.05 0-.13-.02-.136-.068-.01-.066.088-.133.15-.133.08-.031.184-.047.259-.005.019.009.036.03.03.05v.02h.003z"/>'
             '<ellipse cx="11.6" cy="13.6" rx="3.9" ry="5.6" fill="#ffffff"/>'
             '<ellipse cx="10.2" cy="4.5" rx="1.45" ry="1.65" fill="#ffffff"/>'
             '<ellipse cx="13.1" cy="4.3" rx="1.45" ry="1.65" fill="#ffffff"/>'
             '<ellipse cx="5.9" cy="19.8" rx="3.5" ry="2.4" fill="#f0a04b"/>'
             '<ellipse cx="18.2" cy="19.6" rx="3.4" ry="2.4" fill="#f0a04b"/>'
             '<ellipse cx="11.7" cy="6.5" rx="2.4" ry="1.15" fill="#f0a04b"/>'
             '<g transform="translate(12,12) scale(0.962) translate(-12,-12)">'
             '<path fill="#0b0d10" fill-rule="evenodd" d="M12.504 0c-.155 0-.315.008-.48.021-4.226.333-3.105 4.807-3.17 6.298-.076 1.092-.3 1.953-1.05 3.02-.885 1.051-2.127 2.75-2.716 4.521-.278.832-.41 1.684-.287 2.489a.424.424 0 00-.11.135c-.26.268-.45.6-.663.839-.199.199-.485.267-.797.4-.313.136-.658.269-.864.68-.09.189-.136.394-.132.602 0 .199.027.4.055.536.058.399.116.728.04.97-.249.68-.28 1.145-.106 1.484.174.334.535.47.94.601.81.2 1.91.135 2.774.6.926.466 1.866.67 2.616.47.526-.116.97-.464 1.208-.946.587-.003 1.23-.269 2.26-.334.699-.058 1.574.267 2.577.2.025.134.063.198.114.333l.003.003c.391.778 1.113 1.132 1.884 1.071.771-.06 1.592-.536 2.257-1.306.631-.765 1.683-1.084 2.378-1.503.348-.199.629-.469.649-.853.023-.4-.2-.811-.714-1.376v-.097l-.003-.003c-.17-.2-.25-.535-.338-.926-.085-.401-.182-.786-.492-1.046h-.003c-.059-.054-.123-.067-.188-.135a.357.357 0 00-.19-.064c.431-1.278.264-2.55-.173-3.694-.533-1.41-1.465-2.638-2.175-3.483-.796-1.005-1.576-1.957-1.56-3.368.026-2.152.236-6.133-3.544-6.139zm.529 3.405h.013c.213 0 .396.062.584.198.19.135.33.332.438.533.105.259.158.459.166.724 0-.02.006-.04.006-.06v.105a.086.086 0 01-.004-.021l-.004-.024a1.807 1.807 0 01-.15.706.953.953 0 01-.213.335.71.71 0 00-.088-.042c-.104-.045-.198-.064-.284-.133a1.312 1.312 0 00-.22-.066c.05-.06.146-.133.183-.198.053-.128.082-.264.088-.402v-.02a1.21 1.21 0 00-.061-.4c-.045-.134-.101-.2-.183-.333-.084-.066-.167-.132-.267-.132h-.016c-.093 0-.176.03-.262.132a.8.8 0 00-.205.334 1.18 1.18 0 00-.09.4v.019c.002.089.008.179.02.267-.193-.067-.438-.135-.607-.202a1.635 1.635 0 01-.018-.2v-.02a1.772 1.772 0 01.15-.768c.082-.22.232-.406.43-.533a.985.985 0 01.594-.2zm-2.962.059h.036c.142 0 .27.048.399.135.146.129.264.288.344.465.09.199.14.4.153.667v.004c.007.134.006.2-.002.266v.08c-.03.007-.056.018-.083.024-.152.055-.274.135-.393.2.012-.09.013-.18.003-.267v-.015c-.012-.133-.04-.2-.082-.333a.613.613 0 00-.166-.267.248.248 0 00-.183-.064h-.021c-.071.006-.13.04-.186.132a.552.552 0 00-.12.27.944.944 0 00-.023.33v.015c.012.135.037.2.08.334.046.134.098.2.166.268.01.009.02.018.034.024-.07.057-.117.07-.176.136a.304.304 0 01-.131.068 2.62 2.62 0 01-.275-.402 1.772 1.772 0 01-.155-.667 1.759 1.759 0 01.08-.668 1.43 1.43 0 01.283-.535c.128-.133.26-.2.418-.2zm1.37 1.706c.332 0 .733.065 1.216.399.293.2.523.269 1.052.468h.003c.255.136.405.266.478.399v-.131a.571.571 0 01.016.47c-.123.31-.516.643-1.063.842v.002c-.268.135-.501.333-.775.465-.276.135-.588.292-1.012.267a1.139 1.139 0 01-.448-.067 3.566 3.566 0 01-.322-.198c-.195-.135-.363-.332-.612-.465v-.005h-.005c-.4-.246-.616-.512-.686-.71-.07-.268-.005-.47.193-.6.224-.135.38-.271.483-.336.104-.074.143-.102.176-.131h.002v-.003c.169-.202.436-.47.839-.601.139-.036.294-.065.466-.065zm2.8 2.142c.358 1.417 1.196 3.475 1.735 4.473.286.534.855 1.659 1.102 3.024.156-.005.33.018.513.064.646-1.671-.546-3.467-1.089-3.966-.22-.2-.232-.335-.123-.335.59.534 1.365 1.572 1.646 2.757.13.535.16 1.104.021 1.67.067.028.135.06.205.067 1.032.534 1.413.938 1.23 1.537v-.043c-.06-.003-.12 0-.18 0h-.016c.151-.467-.182-.825-1.065-1.224-.915-.4-1.646-.336-1.77.465-.008.043-.013.066-.018.135-.068.023-.139.053-.209.064-.43.268-.662.669-.793 1.187-.13.533-.17 1.156-.205 1.869v.003c-.02.334-.17.838-.319 1.35-1.5 1.072-3.58 1.538-5.348.334a2.645 2.645 0 00-.402-.533 1.45 1.45 0 00-.275-.333c.182 0 .338-.03.465-.067a.615.615 0 00.314-.334c.108-.267 0-.697-.345-1.163-.345-.467-.931-.995-1.788-1.521-.63-.4-.986-.87-1.15-1.396-.165-.534-.143-1.085-.015-1.645.245-1.07.873-2.11 1.274-2.763.107-.065.037.135-.408.974-.396.751-1.14 2.497-.122 3.854a8.123 8.123 0 01.647-2.876c.564-1.278 1.743-3.504 1.836-5.268.048.036.217.135.289.202.218.133.38.333.59.465.21.201.477.335.876.335.039.003.075.006.11.006.412 0 .73-.134.997-.268.29-.134.52-.334.74-.4h.005c.467-.135.835-.402 1.044-.7zm2.185 8.958c.037.6.343 1.245.882 1.377.588.134 1.434-.333 1.791-.765l.211-.01c.315-.007.577.01.847.268l.003.003c.208.199.305.53.391.876.085.4.154.78.409 1.066.486.527.645.906.636 1.14l.003-.007v.018l-.003-.012c-.015.262-.185.396-.498.595-.63.401-1.746.712-2.457 1.57-.618.737-1.37 1.14-2.036 1.191-.664.053-1.237-.2-1.574-.898l-.005-.003c-.21-.4-.12-1.025.056-1.69.176-.668.428-1.344.463-1.897.037-.714.076-1.335.195-1.814.12-.465.308-.797.641-.984l.045-.022zm-10.814.049h.01c.053 0 .105.005.157.014.376.055.706.333 1.023.752l.91 1.664.003.003c.243.533.754 1.064 1.189 1.637.434.598.77 1.131.729 1.57v.006c-.057.744-.48 1.148-1.125 1.294-.645.135-1.52.002-2.395-.464-.968-.536-2.118-.469-2.857-.602-.369-.066-.61-.2-.723-.4-.11-.2-.113-.602.123-1.23v-.004l.002-.003c.117-.334.03-.752-.027-1.118-.055-.401-.083-.71.043-.94.16-.334.396-.4.69-.533.294-.135.64-.202.915-.47h.002v-.002c.256-.268.445-.601.668-.838.19-.201.38-.336.663-.336zm7.159-9.074c-.435.201-.945.535-1.488.535-.542 0-.97-.267-1.28-.466-.154-.134-.28-.268-.373-.335-.164-.134-.144-.333-.074-.333.109.016.129.134.199.2.096.066.215.2.36.333.292.2.68.467 1.167.467.485 0 1.053-.267 1.398-.466.195-.135.445-.334.648-.467.156-.136.149-.267.279-.267.128.016.034.134-.147.332a8.097 8.097 0 01-.69.468zm-1.082-1.583V5.64c-.006-.02.013-.042.029-.05.074-.043.18-.027.26.004.063 0 .16.067.15.135-.006.049-.085.066-.135.066-.055 0-.092-.043-.141-.068-.052-.018-.146-.008-.163-.065zm-.551 0c-.02.058-.113.049-.166.066-.047.025-.086.068-.14.068-.05 0-.13-.02-.136-.068-.01-.066.088-.133.15-.133.08-.031.184-.047.259-.005.019.009.036.03.03.05v.02h.003z"/></g></g>')
    s.append(f'<text x="62" y="28" font-family="{FONT}" font-size="10.5" letter-spacing="1.6" '
             f'fill="#8b949e" font-weight="600">M2582 · SM8735 · QUALCOMM</text>')
    s.append(f'<text x="62" y="55" font-family="{FONT}" font-size="21" font-weight="700" '
             f'fill="#f0f6fc">MEIZU 22 · MAINLINE LINUX</text>')

    pct = f"{n_done / n_all * 100:.0f}%"
    cnt = f"{n_done} / {n_all}"
    right = W - M - 6
    s.append(f'<text x="{right:.1f}" y="50" text-anchor="end" font-family="{FONT}" font-size="13" '
             f'font-weight="600" fill="#8b949e">{cnt}</text>')
    s.append(f'<text x="{right - tw(cnt, 13) - 10:.1f}" y="50" text-anchor="end" '
             f'font-family="{FONT}" font-size="22" font-weight="700" '
             f'fill="{FILL["done"]}">{pct}</text>')

    lx = W - M - 8
    for key, lab in ((T, "Not adapted"), (U, "Partial"), (D, "Adapted")):
        wl = tw(lab, 9.5)
        s.append(f'<text x="{lx:.1f}" y="70" text-anchor="end" font-family="{FONT}" '
                 f'font-size="9.5" fill="#8b949e">{lab}</text>')
        s.append(f'<rect x="{lx - wl - 14:.1f}" y="62" width="9" height="9" rx="2" fill="{FILL[key]}"/>')
        lx -= wl + 34

    top = 84
    stage_weights = [sum(demand(it) for it in items) for _, _, items in STAGES]
    rects = squarify(stage_weights, M, top, W - 2 * M, H - top - M)

    for (code, name, items), (sx, sy, sw, sh) in zip(STAGES, rects):
        s.append(f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{sh:.1f}" '
                 f'fill="{BG}" stroke="#5b6b7c" stroke-width="4"/>')
        done = sum(1 for it in items if item_state(it) == D)
        s.append(f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{STAGE_HEAD}" '
                 f'fill="{STAGE_BG}"/>')
        s.append(f'<line x1="{sx:.1f}" y1="{sy + STAGE_HEAD:.1f}" x2="{sx + sw:.1f}" '
                 f'y2="{sy + STAGE_HEAD:.1f}" stroke="{BORDER}" stroke-width="1"/>')
        s.append(f'<text x="{sx + 5:.1f}" y="{sy + 15:.1f}" font-family="{FONT}" font-size="11.5" '
                 f'font-weight="700" fill="#e6edf3">{code}</text>')
        s.append(f'<text x="{sx + 26:.1f}" y="{sy + 15:.1f}" font-family="{FONT}" font-size="11" '
                 f'fill="#c9d1d9">{name}</text>')
        s.append(f'<text x="{sx + sw - 6:.1f}" y="{sy + 15:.1f}" text-anchor="end" '
                 f'font-family="{FONT}" font-size="10" fill="#8b949e">{done}/{len(items)}</text>')

        iy, ih = sy + STAGE_HEAD, sh - STAGE_HEAD
        items = sorted(items, key=lambda it: -demand(it))
        iweights = [demand(it) for it in items]
        for item, (ix, iyy, iw, ihh) in zip(items, squarify(iweights, sx, iy, sw, ih)):
            _, title, st, subs = item
            if subs is None:
                s.append(f'<rect x="{ix:.1f}" y="{iyy:.1f}" width="{iw:.1f}" height="{ihh:.1f}" '
                         f'fill="{FILL[st]}" stroke="{BORDER}" stroke-width="1"/>')
                fs = fit_fs(title, iw, ihh, 4)
                s.append(label(ix, iyy, iw, ihh, title, fs, INK[st], pad=4, center=True))
            else:
                s.append(f'<rect x="{ix:.1f}" y="{iyy:.1f}" width="{iw:.1f}" height="{ihh:.1f}" '
                         f'fill="{BG}" stroke="{BORDER}" stroke-width="1"/>')
                s.append(label(ix, iyy, iw, ITEM_HEAD, title, 8.6, "#c9d1d9", pad=2, weight=600))
                cy, ch = iyy + ITEM_HEAD, ihh - ITEM_HEAD
                n = len(subs)
                cols = max(1, min(n, round(math.sqrt(n * iw / max(ch, 1)))))
                rows = (n + cols - 1) // cols
                rh = ch / rows
                cells = []
                for r in range(rows):
                    k = min(cols, n - r * cols)
                    for c in range(k):
                        cells.append((ix + c * iw / k, cy + r * rh, iw / k, rh))
                for (slabel, sstate), (cx, cyy, cw, chh) in zip(subs, cells):
                    s.append(f'<rect x="{cx:.1f}" y="{cyy:.1f}" width="{cw:.1f}" height="{chh:.1f}" '
                             f'fill="{FILL[sstate]}" stroke="{BORDER}" stroke-width="1"/>')
                    fs = fit_fs(slabel, cw, chh, 3)
                    s.append(label(cx, cyy, cw, chh, slabel, fs, INK[sstate],
                                   pad=3, center=True))
    defs = "".join(
        f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/></clipPath>'
        for cid, x, y, w, h in CLIPS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}"><defs>{defs}</defs>' + "".join(s) + "</svg>")


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(outdir, exist_ok=True)
    svg = os.path.join(outdir, "progress-dark.svg")
    png = os.path.join(outdir, "progress-dark.png")
    with open(svg, "w", encoding="utf-8") as f:
        f.write(build())
    subprocess.run(["rsvg-convert", "-w", str(W * 2), "-o", png, svg], check=True)
    print("wrote", os.path.relpath(svg, REPO))
    print("wrote", os.path.relpath(png, REPO))


if __name__ == "__main__":
    main()
