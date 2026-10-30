"""Figure 3 (draft): HBB label limitations. Columns = examples, rows = pre / post."""
import sys, pickle, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams.update({'font.family': 'Arial', 'font.size': 8})
cr = pickle.load(open(sys.argv[1], 'rb')); OUT = sys.argv[2]
img = lambda a: np.clip(np.moveaxis(a, 0, -1) / 4000, 0, 1)
HBB, FLAG = '#ff3b30', '#00e5ff'
ex = [(30, '(a) Coarse perimeter', 'Main Range NP (QPWS), Mt Barney area\n45 vertices for 2,774 ha (one per ~670 m)', 'coarse'),
      (12, '(b) Burnt area outside perimeter', 'Keilira (SA DEW), Jan 2020\n~160 ha burnt strip outside the record', 'miss'),
      (24, '(c) Unburnt area inside perimeter', 'Keilira (SA DEW), Jan 2020\n~250 ha of paddocks unchanged since pre-fire', 'over')]
fig, ax = plt.subplots(2, 3, figsize=(7.2, 5.55), dpi=300, gridspec_kw=dict(hspace=0.05, wspace=0.04, left=0.06, right=0.995, top=0.865, bottom=0.075))
for j, (i, title, sub, kind) in enumerate(ex):
    c = cr[i]
    for r, key in enumerate(('pre', 'post')):
        a = ax[r, j]; a.imshow(img(c[key]), interpolation='lanczos'); a.set_xlim(0, 400); a.set_ylim(400, 0); a.axis('off')
        if r == 1:
            for h in c['hbb']:
                if h['sug'] == 'drop' and kind != 'coarse': continue
                if kind == 'coarse' and h['cand'] != '1920-11-005': continue
                for ring in h['rings']:
                    a.plot(ring[:, 0], ring[:, 1], color=HBB, lw=0.9)
                    if kind == 'coarse': a.plot(ring[:, 0], ring[:, 1], 'o', color='white', mec=HBB, ms=2.4, mew=0.6)
            for ring in c['blob']:
                a.plot(ring[:, 0], ring[:, 1], color=FLAG, lw=0.9, ls=(0, (2.5, 1.5)))
        km = 2 if c['km'] < 12 else 5; px = km / c['km'] * 400
        a.plot([385 - px, 385], [385, 385], color='white', lw=2, solid_capstyle='butt')
        a.text(385 - px / 2, 375, f'{km} km', color='white', ha='center', va='bottom', fontsize=7)
    ax[0, j].set_title(title, loc='left', fontsize=8.5, fontweight='bold', pad=24)
    ax[0, j].text(0, 1.015, sub, transform=ax[0, j].transAxes, fontsize=6.5, color='#555', va='bottom')
d = cr[ex[1][0]]['dates']; d0 = cr[ex[0][0]]['dates']
for r, lab in enumerate(('Pre-fire', 'Post-fire')):
    fig.text(0.03, 0.865 - (r + 0.5) * (0.79 / 2), lab, rotation=90, ha='center', va='center', fontsize=8.5, fontweight='bold')
fig.legend(handles=[Line2D([], [], color=HBB, lw=1.2, label='HBB perimeter'),
                    Line2D([], [], color=HBB, marker='o', mfc='white', ms=3.5, lw=1.2, label='HBB vertices (a)'),
                    Line2D([], [], color=FLAG, lw=1.2, ls=(0, (2.5, 1.5)), label='Area discussed (b, c)')],
           loc='lower center', ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.005))
fig.savefig(OUT, dpi=300, facecolor='white'); print('wrote', OUT)
