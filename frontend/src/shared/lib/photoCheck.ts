export type PhotoIssue = 'small' | 'dark' | 'blurry';

const SAMPLE_WIDTH = 400;
const MIN_SHORT_SIDE = 700;
const MIN_BRIGHTNESS = 45;
// Printed bills are sharp text on paper, so even a soft phone photo scores well above this.
const MIN_SHARPNESS = 20;

function toGrey(data: Uint8ClampedArray, size: number): { grey: Float32Array; brightness: number } {
  const grey = new Float32Array(size);
  let total = 0;
  for (let i = 0; i < size; i += 1) {
    const v = 0.299 * (data[i * 4] ?? 0) + 0.587 * (data[i * 4 + 1] ?? 0) + 0.114 * (data[i * 4 + 2] ?? 0);
    grey[i] = v;
    total += v;
  }
  return { grey, brightness: total / size };
}

/** Variance of a 4-neighbour Laplacian: low when edges are soft, which is what blur looks like. */
function sharpness(grey: Float32Array, width: number, height: number): number {
  const at = (i: number) => grey[i] ?? 0;
  let sum = 0;
  let sumSq = 0;
  let n = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const lap = at(i - 1) + at(i + 1) + at(i - width) + at(i + width) - 4 * at(i);
      sum += lap;
      sumSq += lap * lap;
      n += 1;
    }
  }
  return n ? sumSq / n - (sum / n) ** 2 : 0;
}

/**
 * A quick look on the phone before upload, so an obviously bad photo is retaken now instead of after a round trip.
 * Returns null when the photo looks fine or cannot be decoded here (PDFs, HEIC); the server still checks everything.
 */
export async function checkPhoto(file: File): Promise<PhotoIssue | null> {
  if (!file.type.startsWith('image/')) return null;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return null;
  }
  if (Math.min(bitmap.width, bitmap.height) < MIN_SHORT_SIDE) {
    bitmap.close();
    return 'small';
  }
  const width = SAMPLE_WIDTH;
  const height = Math.max(3, Math.round((bitmap.height / bitmap.width) * width));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  context?.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  if (!context) return null;
  const { grey, brightness } = toGrey(context.getImageData(0, 0, width, height).data, width * height);
  if (brightness < MIN_BRIGHTNESS) return 'dark';
  return sharpness(grey, width, height) < MIN_SHARPNESS ? 'blurry' : null;
}
