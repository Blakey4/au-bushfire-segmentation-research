"""Figure 2: dataset structure. Seasons > events > (pre, post, screened label); one event in full."""
import sys, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, FancyBboxPatch
from matplotlib.lines import Line2D
plt.rcParams.update({'font.family': 'Arial', 'font.size': 8})
z = np.load(sys.argv[1]); OUT = sys.argv[2]

W, H = 7.2, 7.75
fig = plt.figure(figsize=(W, H), dpi=300)
INK, MUTED, RULE = '#1f2328', '#6b7280', '#c9ccd1'
BURNT, UNBURNT, IGN = '#b3261e', '#ece8df', '#9a9a9a'
lab_cmap = ListedColormap([UNBURNT, BURNT, IGN, IGN])
img = lambda a: np.clip(np.moveaxis(a, 0, -1) / 4000, 0, 1)

LEFT = 1.80                  # inches reserved for the season/event tree
BIG, GAP, SMALL = 1.70, 0.10, 0.78
col_x = [LEFT + i * (BIG + GAP) for i in range(3)]          # column left edges
col_c = [x + BIG / 2 for x in col_x]                        # column centres
fx, fy = lambda x: x / W, lambda y: y / H                  # inches -> figure fraction (y from top)
T = lambda y: 1 - y / H


def tile(x, y, s, data, cmap=None):
    ax = fig.add_axes([fx(x), T(y + s), fx(s), fy(s)])
    if cmap is None:
        ax.imshow(img(data), interpolation='lanczos')
    else:
        ax.imshow(np.where(data == 3, 2, data), cmap=cmap, vmin=0, vmax=3, interpolation='nearest')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color('#555'); sp.set_linewidth(0.5)


SAME_EVENT = {'1920-01'}     # other HBB records here are part of the same complex (illustrative, not yet screened)


def triple(code, x_centres, y, s):
    for xc, key, cm in zip(x_centres, ('pre', 'final', 'label'), (None, None, lab_cmap)):
        a = z[f'{code}|{key}']
        if key == 'label' and code in SAME_EVENT:
            a = np.where(a == 2, 1, a)
        tile(xc - s / 2, y, s, a, cm)


def text(x, y, s, **kw):
    fig.text(fx(x), T(y), s, **kw)


def vdots(x, y):
    fig.add_artist(Line2D([fx(x)] * 3, [T(y - 0.07), T(y), T(y + 0.07)], ls='', marker='o', ms=1.8,
                          color=MUTED, transform=fig.transFigure))


# column headers
for xc, h in zip(col_c, ('Pre-fire image', 'Post-fire image', 'Screened label')):
    text(xc, 0.12, h, ha='center', va='top', fontsize=9, fontweight='bold', color=INK)

y = 0.45
tree_x = 0.12


def season(y, name):
    fig.add_artist(FancyBboxPatch((fx(0.02), T(y + 0.30)), fx(W - 0.04), fy(0.30),
                                  boxstyle='round,pad=0,rounding_size=0.004', fc='#f2f3f5', ec='none',
                                  transform=fig.transFigure))
    text(0.12, y + 0.15, name, va='center', fontsize=9, fontweight='bold', color=INK)
    return y + 0.30


def branch(y_top, y_mid):
    fig.add_artist(Line2D([fx(tree_x + 0.05)] * 2, [T(y_top), T(y_mid)], color=RULE, lw=0.9))
    fig.add_artist(Line2D([fx(tree_x + 0.05), fx(tree_x + 0.22)], [T(y_mid)] * 2, color=RULE, lw=0.9))


def event(y, s, name, meta, code, top):
    mid = y + s / 2
    branch(top, mid)
    text(tree_x + 0.30, mid - (0.05 if meta else 0), name, va='bottom' if meta else 'center',
         fontsize=8.5 if s > 1 else 8, fontweight='bold' if s > 1 else 'normal', color=INK)
    if meta:
        text(tree_x + 0.30, mid + 0.02, meta, va='top', fontsize=7, color=MUTED, linespacing=1.35)
    triple(code, col_c, y, s)
    return y + s


def more(y, top, label='more events'):
    branch(top, y + 0.12)
    text(tree_x + 0.30, y + 0.12, label, va='center', fontsize=7.5, color=MUTED, style='italic')
    for xc in col_c:
        vdots(xc, y + 0.12)
    return y + 0.28


# --- season 1: one event in full -------------------------------------------------------------------
y = season(y, 'Fire season 2019–20')
top = y
y = event(y + 0.10, BIG, 'Kangaroo Island (SA)',
          'Ravine + KI Complex fires\n~200,000 ha\nPre 16 Dec 2019\nPost 30 Jan 2020', '1920-01', top)
y = event(y + 0.10, SMALL, 'Cudlee Creek (SA)', None, '1920-09', top)
y = event(y + 0.08, SMALL, 'Keilira (SA)', None, '1920-10', top)
y = more(y + 0.04, top)

# --- season 2: compact ------------------------------------------------------------------------------
y = season(y + 0.06, 'Fire season 2023–24')
top = y
y = event(y + 0.10, SMALL, 'Bayindeen–Rocky Road (VIC)', None, '2324-03', top)
y = event(y + 0.08, SMALL, 'Coolagolite Road (NSW)', None, '2324-05', top)
y = more(y + 0.04, top)

# --- further seasons ---------------------------------------------------------------------------------
vdots(W / 2 - 1.25, y + 0.16)
text(W / 2 - 1.1, y + 0.16, 'further fire seasons, same structure', ha='left', va='center',
     fontsize=8, color=MUTED, style='italic')
y += 0.36

fig.legend(handles=[Patch(fc=BURNT, ec='#555', lw=0.4, label='Burnt (this event)'),
                    Patch(fc=UNBURNT, ec='#555', lw=0.4, label='Unburnt'),
                    Patch(fc=IGN, ec='#555', lw=0.4, label='Ignored (other fire, cloud)')],
           loc='upper center', bbox_to_anchor=(0.5, T(y)), ncol=3, frameon=False, fontsize=7.5,
           handlelength=1.2, columnspacing=1.6)
fig.savefig(OUT, dpi=300, facecolor='white')
print('wrote', OUT, f'content height {y + 0.35:.2f} in of {H}')
