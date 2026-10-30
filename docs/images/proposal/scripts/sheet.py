import sys, pickle, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
cr = pickle.load(open(sys.argv[1], 'rb')); sel = sys.argv[3].split(',') if len(sys.argv) > 3 else None
if sel: cr = [cr[int(i)] for i in sel]
img = lambda a: np.clip(np.moveaxis(a, 0, -1) / 4000, 0, 1)
COL = {'target': '#ff3b30', 'other': '#ffd60a', 'drop': '#bbbbbb'}
n = len(cr); cols = 2; rows = (n + cols - 1) // cols
fig, ax = plt.subplots(rows, cols * 2, figsize=(cols * 2 * 3.2, rows * 3.4))
ax = np.atleast_2d(ax)
for i, c in enumerate(cr):
    a0, a1 = ax[i // cols, (i % cols) * 2], ax[i // cols, (i % cols) * 2 + 1]
    a0.imshow(img(c['pre'])); a1.imshow(img(c['post']))
    for h in c['hbb']:
        for r in h['rings']:
            a1.plot(r[:, 0], r[:, 1], color=COL.get(h['sug'], 'w'), lw=0.8, ls='-' if h['sug'] != 'drop' else ':')
    for r in c['blob']:
        a1.plot(r[:, 0], r[:, 1], color='#00e5ff', lw=0.8)
    names = '; '.join(sorted({f"{h['name'][:22]}({h['sug'][0]})" for h in c['hbb']}))[:110]
    a0.set_title(f"[{sel[i] if sel else i}] {c['fire']} {c['title']} {c['km']:.0f}km", fontsize=7, loc='left')
    a1.set_title(names, fontsize=5, loc='left')
for a in ax.flat: a.set_xticks([]); a.set_yticks([]); a.set_xlim(0, 400); a.set_ylim(400, 0)
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=int(sys.argv[4]) if len(sys.argv) > 4 else 80)
