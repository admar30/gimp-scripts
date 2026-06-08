export const MAX_INPUT_BYTES = 250 * 1024 * 1024;
export const MAX_DECODED_PIXELS = 100_000_000;
export const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp"];
export const FILE_ACCEPT = "image/jpeg,image/png,image/webp,image/avif,image/gif,image/bmp,.jpg,.jpeg,.png,.webp,.avif,.gif,.bmp";

export interface DecodedImage {
  source: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
}

export function validateImageFile(file: File): void {
  const lowerName = file.name.toLowerCase();
  if (lowerName.endsWith(".svg") || file.type === "image/svg+xml") {
    throw new Error("SVG input is not supported. Export it to PNG, JPEG, WebP, AVIF, GIF, or BMP first.");
  }
  if (!ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))) {
    throw new Error("Unsupported file type. Choose a JPEG, PNG, WebP, AVIF, GIF, or BMP image.");
  }
  if (file.size > MAX_INPUT_BYTES) {
    throw new Error("This file exceeds the 250 MiB input limit.");
  }
}

export async function decodeImage(file: File): Promise<DecodedImage> {
  validateImageFile(file);
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const pixels = bitmap.width * bitmap.height;
    if (pixels > MAX_DECODED_PIXELS) {
      bitmap.close();
      throw new Error("The decoded image exceeds the 100 megapixel safety limit.");
    }
    return {
      source: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      close: () => bitmap.close(),
    };
  } catch (error) {
    if (error instanceof Error && error.message.includes("safety limit")) throw error;
    return decodeWithImageElement(file);
  }
}

async function decodeWithImageElement(file: File): Promise<DecodedImage> {
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.decoding = "async";
  image.src = url;
  try {
    await image.decode();
    if (image.naturalWidth * image.naturalHeight > MAX_DECODED_PIXELS) {
      throw new Error("The decoded image exceeds the 100 megapixel safety limit.");
    }
    return {
      source: image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      close: () => URL.revokeObjectURL(url),
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    if (error instanceof Error && error.message.includes("safety limit")) throw error;
    throw new Error(
      "The browser could not decode this image. Its format may not be supported here.",
      { cause: error },
    );
  }
}
