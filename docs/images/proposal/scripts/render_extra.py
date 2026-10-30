"""3 x 3 grid of the extra views of one fire, rendered by QGIS with the styles/ .qml files."""
import sys, glob, os
from qgis.core import QgsApplication, QgsRasterLayer, QgsMapSettings, QgsMapRendererParallelJob
from qgis.PyQt.QtCore import QSize, Qt, QRect
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QFont
app = QgsApplication([], False); app.initQgis()
D, OUT = sys.argv[1:3]; TITLE = os.environ['VIEW_TITLE']
pre = os.path.basename(glob.glob(f'{D}/*_pre.tif')[0])[:10]; fin = os.path.basename(glob.glob(f'{D}/*_final.tif')[0])[:10]
cells = [('Agriculture · pre-fire', f'{pre}_pre.tif', 'agriculture'), ('Agriculture · post-fire', f'{fin}_final.tif', 'agriculture'),
         ('BAIS2 · pre-fire', f'{pre}_bais2.tif', 'bais2'),
         ('False colour IR · pre-fire', f'{pre}_pre.tif', 'false-colour-ir'), ('False colour IR · post-fire', f'{fin}_final.tif', 'false-colour-ir'),
         ('BAIS2 · post-fire', f'{fin}_bais2.tif', 'bais2'),
         ('NBR · post-fire', f'{fin}_nbr.tif', 'nbr'), ('dNBR', 'dnbr.tif', 'dnbr'), ('RBR', 'rbr.tif', 'rbr')]
W = 620; ref = QgsRasterLayer(f'{D}/{fin}_final.tif', 'r'); ext = ref.extent(); H = int(W * ext.height() / ext.width())
G, TOP = 6, 60
img = QImage(3 * W + 4 * G, TOP + 3 * H + 4 * G, QImage.Format_RGB32); img.fill(QColor('white')); pa = QPainter(img)
pa.setRenderHint(QPainter.Antialiasing)
f = QFont('Arial', 20, QFont.Bold); pa.setFont(f); pa.setPen(QColor('black'))
pa.drawText(QRect(0, 0, img.width(), TOP), Qt.AlignCenter, f'{TITLE}   (pre {pre}, post {fin})')
for i, (lab, fn, st) in enumerate(cells):
    l = QgsRasterLayer(f'{D}/{fn}', st); l.loadNamedStyle(f'styles/{st}.qml')
    ms = QgsMapSettings(); ms.setLayers([l]); ms.setExtent(ext); ms.setOutputSize(QSize(W, H)); ms.setDestinationCrs(l.crs())
    ms.setBackgroundColor(QColor('black'))
    j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished()
    x, y = G + (i % 3) * (W + G), TOP + G + (i // 3) * (H + G)
    pa.drawImage(x, y, j.renderedImage())
    pa.setFont(QFont('Arial', 13, QFont.Bold)); r = pa.fontMetrics().boundingRect(lab)
    pa.setPen(Qt.NoPen); pa.setBrush(QColor(0, 0, 0, 160)); pa.drawRoundedRect(x + 10, y + 10, r.width() + 18, r.height() + 10, 5, 5)
    pa.setPen(QColor('white')); pa.drawText(x + 19, y + 15 + pa.fontMetrics().ascent(), lab)
pa.end(); img.save(OUT); print('wrote', OUT); app.exitQgis()
