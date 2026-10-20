function svgPng(svg) {
  return new Promise((resolve) => {
    if (!svg) { resolve(null); return; }
    const data = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 1000;
      canvas.height = Math.max(400, Math.round(1000 * image.height / image.width));
      const context = canvas.getContext('2d');
      context.fillStyle = '#f5faf8';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/png'));
    };
    image.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    image.src = url;
  });
}

export async function captureSceneImages(root = document) {
  const top = root.querySelector('svg[aria-label^="План сверху"]');
  const twoD = await svgPng(top);
  const webgl = root.querySelector('.scene-preview-canvas');
  let threeD = null;
  if (webgl && webgl.width > 0 && webgl.height > 0) {
    try { threeD = webgl.toDataURL('image/png'); } catch { /* Current 3D snapshot stays unavailable. */ }
  }
  return { two_d_png: twoD, three_d_png: threeD,
    three_d_source: threeD ? 'CURRENT_WEBGL_CANVAS' : null };
}
