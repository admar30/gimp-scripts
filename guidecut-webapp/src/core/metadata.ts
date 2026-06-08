import * as exifr from "exifr";

export interface PdfMetadata {
  title?: string;
  author?: string;
  subject?: string;
  keywords?: string[];
}

function firstText(...values: unknown[]): string | undefined {
  const value = values.find((candidate) => typeof candidate === "string" && candidate.trim());
  return typeof value === "string" ? value.trim() : undefined;
}

export async function readPdfMetadata(file: File): Promise<PdfMetadata> {
  try {
    const data = await exifr.parse(file, {
      tiff: true,
      exif: true,
      iptc: true,
      xmp: true,
      icc: true,
      translateValues: false,
    });
    if (!data) return {};
    const keywordsValue = data.Keywords ?? data.Subject;
    const keywords = Array.isArray(keywordsValue)
      ? keywordsValue.map(String)
      : typeof keywordsValue === "string"
        ? keywordsValue.split(/[,;]/).map((value: string) => value.trim()).filter(Boolean)
        : undefined;
    return {
      title: firstText(data.Title, data.ObjectName, data.ImageDescription),
      author: firstText(data.Author, data.Artist, data.Creator, data.Byline),
      subject: firstText(data.Description, data.Caption, data.Subject),
      keywords,
    };
  } catch {
    return {};
  }
}
