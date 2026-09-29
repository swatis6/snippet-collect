
import argparse
import os
import sys
 
from waterfall import within_file_rows, combined_within_rows, _iq_files
 
 
def gather(paths):
    files = []
    for p in paths:
        p = p.strip().strip('"')
        if os.path.isdir(p):
            files += _iq_files(p)
        elif p.lower().endswith('.iq') and os.path.exists(p):
            files.append(p)
    return files
 
 
def _parse_drop(data):
    out, buf, i = [], '', 0
    while i < len(data):
        c = data[i]
        if c == '{':
            j = data.find('}', i)
            out.append(data[i + 1:j])
            i = j + 1
        elif c == ' ':
            if buf:
                out.append(buf)
                buf = ''
            i += 1
        else:
            buf += c
            i += 1
    if buf:
        out.append(buf)
    return out
 
 
def draw(ax, files, nfft, overlap, labels=True):
    files = sorted(files, key=os.path.basename)
    ax.clear()
    ax.set_xlabel('Frequency (MHz)')
    if len(files) == 1:
        data, ext = within_file_rows(files[0], nfft, overlap)
        ax.set_ylabel('Time (ms)')
        if data.size:
            f0, f1, dur_ms = ext
            ax.imshow(data, aspect='auto', origin='lower',
                      extent=[f0, f1, 0, dur_ms], cmap='viridis')
        title = f'{os.path.basename(files[0])}  ({data.shape[0]} rows)'
        ax.set_title(title)
        png = os.path.splitext(files[0])[0] + '_waterfall.png'
        return title, png
 
    data, ext, boundaries = combined_within_rows(files, nfft, overlap)
    ax.set_ylabel('Row (files stacked, filename order)')
    if data.size:
        f0, f1 = ext
        ax.imshow(data, aspect='auto', origin='lower',
                  extent=[f0, f1, 0, data.shape[0]], cmap='viridis')
        prev = 0
        for end, name in boundaries:
            if end != data.shape[0]:
                ax.axhline(end, color='w', lw=0.6, alpha=0.6) 
            if labels:
                ax.text(f0, (prev + end) / 2, ' ' + name, color='w', fontsize=7,
                        va='center', ha='left')
            prev = end
    title = f'{len(files)} files combined  ({data.shape[0]} rows)'
    ax.set_title(title)
    png = os.path.join(os.path.dirname(files[0]), 'combined_waterfall.png')
    return title, png
 
 
def _autosave(files, nfft, overlap, labels=True):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    f = Figure(figsize=(8, 6))
    FigureCanvasAgg(f)
    ax = f.add_subplot(111)
    _title, png = draw(ax, files, nfft, overlap, labels)
    f.tight_layout()
    try:
        f.savefig(png, dpi=120)
        print(f'saved -> {png}')
    except Exception as e:
        print(f'save failed: {e}')
    return png
 
 
def run_gui(nfft=1024, overlap=0.5, labels=True):
    import matplotlib
    matplotlib.use('TkAgg')
    import tkinter as tk
    from tkinter import filedialog
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
 
    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES
        root = TkinterDnD.Tk()
        has_dnd = True
    except Exception:
        root = tk.Tk()
        has_dnd = False
 
    root.title('IQ Waterfall - drag & drop')
    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.set_xlabel('Frequency (MHz)')
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(side='top', fill='both', expand=True)
    NavigationToolbar2Tk(canvas, root)
 
    show_labels = tk.BooleanVar(value=labels)
    last = {'files': []}
 
    def render(files):
        if files:
            last['files'] = files
        if not last['files']:
            return
        draw(ax, last['files'], nfft, overlap, show_labels.get())
        fig.tight_layout()
        canvas.draw()
        _autosave(last['files'], nfft, overlap, show_labels.get())
 
    def add_files():
        render(gather(list(filedialog.askopenfilenames(filetypes=[('IQ files', '*.iq')]))))
 
    def add_folder():
        d = filedialog.askdirectory()
        render(gather([d]) if d else [])
 
    def save_png():
        p = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG', '*.png')])
        if p:
            fig.savefig(p, dpi=120)
 
    def on_drop(event):
        render(gather(_parse_drop(event.data)))
 
    bar = tk.Frame(root)
    bar.pack(side='bottom', fill='x')
    tk.Button(bar, text='Add files...', command=add_files).pack(side='left')
    tk.Button(bar, text='Add folder...', command=add_folder).pack(side='left')
    tk.Button(bar, text='Save PNG', command=save_png).pack(side='left')
    tk.Checkbutton(bar, text='filenames', variable=show_labels,
                   command=lambda: render(None)).pack(side='left')
    tk.Label(bar, text=('drop .iq files or a folder onto the plot' if has_dnd
                        else 'tkinterdnd2 not installed - use Add files / Add folder')).pack(side='right')
 
    if has_dnd:
        w = canvas.get_tk_widget()
        w.drop_target_register(DND_FILES)
        w.dnd_bind('<<Drop>>', on_drop)
 
    root.mainloop()
 
 
def main():
    ap = argparse.ArgumentParser(description='Drag-and-drop within-file IQ waterfall')
    ap.add_argument('paths', nargs='*', help='.iq files or a folder')
    ap.add_argument('--fft', type=int, default=1024, help='FFT size per row (default 1024)')
    ap.add_argument('--overlap', type=float, default=0.5, help='window overlap 0..1 (default 0.5)')
    ap.add_argument('--save', help='save combined PNG to this path (else auto next to files)')
    ap.add_argument('--no-labels', dest='labels', action='store_false',
                    help='hide the filename labels on the stacked plot')
    ap.set_defaults(labels=True)
    args = ap.parse_args()
 
    if not args.paths:
        run_gui(args.fft, args.overlap, args.labels)
        return
 
    files = gather(args.paths)
    if not files:
        print('no .iq files found in:', args.paths)
        return
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    _title, default_png = draw(ax, files, args.fft, args.overlap, args.labels)
    fig.tight_layout()
    out = args.save or default_png
    try:
        fig.savefig(out, dpi=120)
        print(f'saved -> {out}')
    except Exception as e:
        print(f'save failed: {e}')
    plt.show()
 
 
if __name__ == '__main__':
    main()
 