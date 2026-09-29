import argparse
import glob
import os
import time
import xml.etree.ElementTree as ET

import numpy as np


def _read_xml(xml_path):
    sr, scale, center = 40e6, 1.0, 0.0
    try:
        root = ET.parse(xml_path).getroot()
        for tag, cast in (('SampleRate', float), ('ScaleFactor', float), ('CenterFrequency', float)):
            el = root.find(tag)
            if el is not None and el.text:
                val = cast(el.text)
                if tag == 'SampleRate':
                    sr = val
                elif tag == 'ScaleFactor':
                    scale = val
                else:
                    center = val
    except Exception:
        pass
    return sr, scale, center


def load_iq(iq_path):
    xml_path = os.path.splitext(iq_path)[0] + '.xml'
    if not os.path.exists(xml_path):
        return None
    sr, scale, center = _read_xml(xml_path)
    raw = np.fromfile(iq_path, dtype='<i2')
    if raw.size < 2:
        return None
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    z = (i + 1j * q) / 32767.0 / (scale or 1.0)
    return z, sr, center


def spectrum_dbm(z, nfft):
    win = np.hanning(nfft)
    if z.size >= nfft:
        nseg = z.size // nfft
        acc = np.zeros(nfft)
        for k in range(nseg):
            seg = z[k * nfft:(k + 1) * nfft] * win
            acc += np.abs(np.fft.fftshift(np.fft.fft(seg))) ** 2
        psd = acc / (nseg * (win.sum() ** 2))
    else:
        seg = np.zeros(nfft, dtype=complex)
        seg[:z.size] = z
        psd = np.abs(np.fft.fftshift(np.fft.fft(seg * win))) ** 2 / (win.sum() ** 2)
    return 10.0 * np.log10(psd + 1e-30)


def build_rows(iq_paths, nfft=1024):
    rows, sr, center = [], 40e6, 0.0
    for p in iq_paths:
        loaded = load_iq(p)
        if loaded is None:
            continue
        z, sr, center = loaded
        rows.append(spectrum_dbm(z, nfft))
    if not rows:
        return np.empty((0, nfft)), None
    f0 = (center - sr / 2) / 1e6
    f1 = (center + sr / 2) / 1e6
    return np.array(rows), (f0, f1)


def within_file_rows(iq_path, nfft=1024, overlap=0.5):
    loaded = load_iq(iq_path)
    if loaded is None:
        return np.empty((0, nfft)), None
    z, sr, center = loaded
    step = max(1, int(nfft * (1.0 - overlap)))
    win = np.hanning(nfft)
    rows = []
    for start in range(0, max(1, z.size - nfft + 1), step):
        seg = z[start:start + nfft]
        if seg.size < nfft:
            break
        X = np.fft.fftshift(np.fft.fft(seg * win)) / win.sum()
        rows.append(10.0 * np.log10(np.abs(X) ** 2 + 1e-30))
    if not rows:
        rows.append(spectrum_dbm(z, nfft))
    f0 = (center - sr / 2) / 1e6
    f1 = (center + sr / 2) / 1e6
    dur_ms = z.size / sr * 1e3
    return np.array(rows), (f0, f1, dur_ms)


def combined_within_rows(iq_paths, nfft=1024, overlap=0.5):
    paths = sorted(iq_paths, key=os.path.basename)
    blocks, boundaries, extent, centers, total = [], [], None, set(), 0
    for p in paths:
        data, ext = within_file_rows(p, nfft, overlap)
        if not data.size:
            continue
        f0, f1, _dur = ext
        extent = (f0, f1)
        centers.add(round((f0 + f1) / 2, 3))
        blocks.append(data)
        total += data.shape[0]
        boundaries.append((total, os.path.basename(p)))
    if len(centers) > 1:
        print(f'WARNING: files have different Rx centers {sorted(centers)} MHz - '
              f'the frequency axis only matches the first; combined plot may be misleading')
    if not blocks:
        return np.empty((0, nfft)), None, []
    return np.vstack(blocks), extent, boundaries


def _iq_files(folder):
    files = glob.glob(os.path.join(folder, '**', '*.iq'), recursive=True)
    return sorted(files, key=lambda f: os.path.getmtime(f))


def render_static(iq_paths, nfft=1024, save=None, title=None):
    import matplotlib
    if save:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data, extent = build_rows(iq_paths, nfft)
    fig, ax = plt.subplots(figsize=(8, 5))
    if data.size:
        ax.imshow(data, aspect='auto', origin='lower',
                  extent=[extent[0], extent[1], 0, data.shape[0]], cmap='viridis')
    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel('Snippet #')
    ax.set_title(title or 'IQ Waterfall')
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=120)
        print(f'waterfall saved -> {save} ({data.shape[0]} rows)')
    else:
        plt.show()


def run_live(folder, nfft=1024, title=None, poll=0.5, save=None):
    import matplotlib.pyplot as plt
    plt.ion()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel('Snippet #')
    ax.set_title(title or f'IQ Waterfall - {os.path.basename(folder.rstrip("/"))}')
    img, rows, extent, seen = None, [], None, set()
    save_path = save or os.path.join(folder, os.path.basename(folder.rstrip('/\\')) + '_waterfall.png')
    print(f'waterfall live on {folder}  (close the window to stop; PNG -> {save_path})')
    while plt.fignum_exists(fig.number):
        for p in _iq_files(folder):
            if p in seen:
                continue
            loaded = load_iq(p)
            if loaded is None:
                continue
            z, sr, center = loaded
            rows.append(spectrum_dbm(z, nfft))
            seen.add(p)
            extent = ((center - sr / 2) / 1e6, (center + sr / 2) / 1e6)
        if rows:
            data = np.array(rows)
            if img is None:
                img = ax.imshow(data, aspect='auto', origin='lower',
                                extent=[extent[0], extent[1], 0, data.shape[0]], cmap='viridis')
                fig.colorbar(img, ax=ax, label='dBm')
            else:
                img.set_data(data)
                img.set_extent([extent[0], extent[1], 0, data.shape[0]])
                img.autoscale()
            fig.canvas.draw_idle()
        plt.pause(poll)
    if rows:
        try:
            fig.savefig(save_path, dpi=120)
            print(f'waterfall saved -> {save_path} ({len(rows)} rows)')
        except Exception as e:
            print(f'waterfall save failed: {e}')


def main():
    ap = argparse.ArgumentParser(description='IQ snippet waterfall (Signal Hound .iq/.xml)')
    ap.add_argument('paths', nargs='+', help='a folder, or one/more .iq files')
    ap.add_argument('--live', action='store_true', help='watch a folder and add rows live')
    ap.add_argument('--once', action='store_true', help='render current files once, then exit')
    ap.add_argument('--save', help='save a PNG instead of showing (implies once)')
    ap.add_argument('--fft', type=int, default=1024, help='FFT size (default 1024)')
    ap.add_argument('--title', help='window/plot title')
    args = ap.parse_args()

    if args.live and len(args.paths) == 1 and os.path.isdir(args.paths[0]):
        run_live(args.paths[0], args.fft, args.title, save=args.save)
        return

    if len(args.paths) == 1 and os.path.isdir(args.paths[0]):
        files = _iq_files(args.paths[0])
    else:
        files = [p for p in args.paths if p.lower().endswith('.iq')]
    render_static(files, args.fft, save=args.save, title=args.title)


if __name__ == '__main__':
    main()