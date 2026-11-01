export interface ViewBox { x: number; y: number; width: number; height: number }
export interface Size { width: number; height: number }

const MARGIN = 0.03;

/** The whole page, centred, with the pane's shape so that nothing stretches. */
export function fitBox(page: Size, pane: Size): ViewBox {
  const aspect = pane.width / Math.max(pane.height, 1);
  let width = page.width * (1 + 2 * MARGIN);
  let height = page.height * (1 + 2 * MARGIN);
  if (width / height < aspect) width = height * aspect;
  else height = width / aspect;
  return { x: page.width / 2 - width / 2, y: page.height / 2 - height / 2, width, height };
}

/** Closer by `factor` (> 1), keeping the point under the pointer where it is. */
export function zoomAt(box: ViewBox, factor: number, at: { x: number; y: number }): ViewBox {
  const width = box.width / factor;
  const height = box.height / factor;
  return { x: box.x + (box.width - width) * at.x, y: box.y + (box.height - height) * at.y, width, height };
}

/** The page follows the pointer: a drag right moves the view left. */
export function panBy(box: ViewBox, dx: number, dy: number, pane: Size): ViewBox {
  return { ...box, x: box.x - (dx * box.width) / pane.width, y: box.y - (dy * box.height) / pane.height };
}
