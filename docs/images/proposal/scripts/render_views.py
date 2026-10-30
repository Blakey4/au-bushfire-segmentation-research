"""3 x 3 grid of the annotation views of one fire, each labelled on the image."""
import sys, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': 'Arial'})
z = np.load(sys.argv[1]); OUT, TITLE = sys.argv[2], sys.argv[3]
rgb = lambda a: np.nan_to_num(np.clip(np.moveaxis(a, 0, -1) / 4000, 0, 1))
u8 = lambda a: np.moveaxis(a, 0, -1)
panels = [('atm-pen  ·  pre-fire', rgb(z['atm_pre']), {}),
          ('atm-pen  ·  post-fire', rgb(z['atm_final']), {}),
          ('atm-pen highlight', u8(z['atm-pen-highlight']), {}),
          ('swir  ·  pre-fire', rgb(z['swir_pre']), {}),
          ('swir  ·  post-fire', rgb(z['swir_final']), {}),
          ('swir highlight', u8(z['swir-highlight']), {}),
          ('NBR  ·  post-fire', z['nbr_final'], dict(cmap='gray', vmin=-0.5, vmax=0.7)),
          ('NBR2  ·  post-fire', z['nbr2_final'], dict(cmap='gray', vmin=-0.1, vmax=0.4)),
          ('dNBR', z['dnbr'], dict(cmap='inferno', vmin=-0.1, vmax=0.8))]
h, w = z['dnbr'].shape
fig = plt.figure(figsize=(3 * 3.2, 3 * 3.2 * h / w + 0.45), dpi=200)
gs = fig.add_gridspec(3, 3, left=0.005, right=0.995, bottom=0.005, top=1 - 0.45 / fig.get_figheight(), wspace=0.015, hspace=0.015)
for i, (lab, a, kw) in enumerate(panels):
    ax = fig.add_subplot(gs[i // 3, i % 3]); ax.imshow(a, interpolation='lanczos', **kw); ax.axis('off')
    ax.text(0.025, 0.975, lab, transform=ax.transAxes, ha='left', va='top', fontsize=10, fontweight='bold', color='white',
            bbox=dict(fc='black', alpha=0.6, ec='none', boxstyle='round,pad=0.3'))
fig.suptitle(f"{TITLE}   (pre {z['pre_date']}, post {z['final_date']})", y=1 - 0.08 / fig.get_figheight(), va='top', fontsize=12, fontweight='bold')
fig.savefig(OUT, facecolor='white'); print('wrote', OUT)
