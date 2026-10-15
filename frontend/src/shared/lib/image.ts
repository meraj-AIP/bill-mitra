const MAX_SIDE = 1600;

/** Phone photos are often 4 to 12 MB. Shrink before upload; the reader needs about 1600 px. */
export async function shrinkImage(file: File): Promise<Blob> {
  if (!file.type.startsWith('image/')) return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // Most browsers cannot decode HEIC; the server can, so send the original.
    return file;
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size < 2_000_000) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob ?? file), 'image/jpeg', 0.88));
}
