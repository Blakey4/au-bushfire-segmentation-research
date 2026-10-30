import sys, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, ConnectionPatch
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
plt.rcParams.update({'font.family': 'Arial', 'font.size': 8.5, 'hatch.color': '#00e5ff', 'hatch.linewidth': 0.5})
z = np.load(sys.argv[1]); OUT = sys.argv[2]
X0, Y0, S = 60, 74, 512                     # sub-crop of the 640 px window, centred on the valley floor
sub = lambda a: a[..., Y0:Y0 + S, X0:X0 + S]
img = lambda a: np.clip(np.moveaxis(a, 0, -1) / 4000, 0, 1)

def blur(m, k=2):
    m = m.astype(float)
    for _ in range(k):
        p = np.pad(m, 2, mode='edge')
        m = sum(p[i:i + m.shape[0], j:j + m.shape[1]] for i in range(5) for j in range(5)) / 25
    return m

HBB, DNBR, BOX = '#ff3b30', '#00e5ff', '#ffffff'
fig = plt.figure(figsize=(7.2, 7.6), dpi=300)
gs = fig.add_gridspec(2, 3, height_ratios=[1.45, 1], hspace=0.12, wspace=0.04, left=0.01, right=0.99, top=0.97, bottom=0.075)
ax0 = fig.add_subplot(gs[0, :])
full = z['full']; ax0.imshow(img(full))
for m in z['hbb_all_full']:
    if m.any(): ax0.contour(blur(m, 1), levels=[0.5], colors=HBB, linewidths=0.6)
bx, by = 1200 / 2 + X0 / 2, 1300 / 2 + Y0 / 2; bs = S / 2
ax0.add_patch(Rectangle((bx, by), bs, bs, fill=False, ec=BOX, lw=1.4))
ax0.text(bx + bs + 12, by + 10, 'b–d', color=BOX, fontsize=9, fontweight='bold', va='top')
ax0.set_title('(a)  Orroral Valley fire, post-fire image (15 Mar 2020) with HBB perimeters', fontsize=9, loc='left')
km = 10 / 0.04                              # 10 km at 40 m display pixels
h, w = full.shape[1:]
ax0.plot([w - 40 - km, w - 40], [h - 45, h - 45], color='white', lw=2.5, solid_capstyle='butt')
ax0.text(w - 40 - km / 2, h - 60, '10 km', color='white', ha='center', va='bottom', fontsize=8)
ax0.axis('off')

panels = [('(b)  Pre-fire, 16 Dec 2019', sub(z['pre']), False),
          ('(c)  Post-fire, 15 Mar 2020', sub(z['post']), True),
          ('(d)  During fire, 4 Feb 2020', sub(z['dur']), False)]
axs = []
for i, (title, a, lines) in enumerate(panels):
    ax = fig.add_subplot(gs[1, i]); axs.append(ax)
    ax.imshow(img(a)); ax.set_title(title, fontsize=8.5, loc='left'); ax.axis('off')
    if lines:
        for m in z['hbb_all_crop_each']:
            if sub(m).any(): ax.contour(blur(sub(m), 1), levels=[0.5], colors=HBB, linewidths=0.9)
        d = (sub(z['dnbr_post']) > 0.1) & sub(z['ok_post'])
        ax.contourf(blur(d, 2), levels=[0.5, 2], colors='none', hatches=['////'])
        ax.contour(blur(d, 2), levels=[0.5], colors=DNBR, linewidths=0.6)
    else:
        ax.contour(blur(sub(z['valley']), 6), levels=[0.5], colors='white', linewidths=0.9, linestyles='dashed')
    k = 2 / 0.02                            # 2 km at 20 m
    ax.plot([S - 20 - k, S - 20], [S - 22, S - 22], color='white', lw=2, solid_capstyle='butt')
    ax.text(S - 20 - k / 2, S - 30, '2 km', color='white', ha='center', va='bottom', fontsize=7)
    for sp in ax.spines.values(): sp.set_visible(False)
fig.legend(handles=[Line2D([], [], color=HBB, lw=1.4, label='HBB perimeters (agency records)'),
                    Patch(facecolor='none', edgecolor=DNBR, hatch='////', label='Burnt by dNBR > 0.1 (pre vs post)'),
                    Line2D([], [], color='0.3', lw=1.2, ls=(0, (3, 2)), label='Valley grass floor')],
           loc='lower center', ncol=3, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.012))
fig.savefig(OUT, dpi=300, facecolor='white')
print('wrote', OUT)
