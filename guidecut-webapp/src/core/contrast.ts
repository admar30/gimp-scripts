const PRIMARY = ["#0F8F84", "#FFFFFF", "#111111", "#FFD54A", "#FF4D6D"] as const;
const HALOS = ["#111111", "#FFFFFF"] as const;
const HALO_THRESHOLD = 2.5;

function hexToRgb(value: string): [number, number, number] {
  return [
    Number.parseInt(value.slice(1, 3), 16),
    Number.parseInt(value.slice(3, 5), 16),
    Number.parseInt(value.slice(5, 7), 16),
  ];
}

export function relativeLuminance([red, green, blue]: [number, number, number]): number {
  const linear = (channel: number) => {
    const normalized = Math.max(0, Math.min(255, channel)) / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

export function contrastRatio(first: number, second: number): number {
  const light = Math.max(first, second);
  const dark = Math.min(first, second);
  return (light + 0.05) / (dark + 0.05);
}

export function chooseGuideStyle(samples: number[]): { stroke: string; halo: string | null } {
  if (!samples.length) return { stroke: PRIMARY[0], halo: null };
  let stroke: string = PRIMARY[0];
  let score = -1;
  for (const candidate of PRIMARY) {
    const luminance = relativeLuminance(hexToRgb(candidate));
    const worst = Math.min(...samples.map((sample) => contrastRatio(luminance, sample)));
    if (worst > score) {
      stroke = candidate;
      score = worst;
    }
  }
  if (score >= HALO_THRESHOLD) return { stroke, halo: null };
  const halo = HALOS.filter((candidate) => candidate !== stroke).sort((first, second) => {
    const firstScore = Math.min(
      ...samples.map((sample) => contrastRatio(relativeLuminance(hexToRgb(first)), sample)),
    );
    const secondScore = Math.min(
      ...samples.map((sample) => contrastRatio(relativeLuminance(hexToRgb(second)), sample)),
    );
    return secondScore - firstScore;
  })[0];
  return { stroke, halo };
}

export function sampleCanvasLine(
  context: CanvasRenderingContext2D,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): number[] {
  const length = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));
  const count = Math.max(2, Math.min(96, Math.floor(length / 16) + 1));
  const samples: number[] = [];
  for (let index = 0; index < count; index += 1) {
    const ratio = index / (count - 1);
    const x = Math.max(0, Math.min(context.canvas.width - 1, Math.round(x0 + (x1 - x0) * ratio)));
    const y = Math.max(0, Math.min(context.canvas.height - 1, Math.round(y0 + (y1 - y0) * ratio)));
    const pixel = context.getImageData(x, y, 1, 1).data;
    samples.push(relativeLuminance([pixel[0], pixel[1], pixel[2]]));
  }
  return samples;
}
