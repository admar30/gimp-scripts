import { useEffect, useRef, useState } from "react";
import { chooseGuideStyle, sampleCanvasLine } from "../core/contrast";
import {
  buildGridGeometry,
  effectiveCrop,
  type ExpandOptions,
  type GridSelection,
} from "../core/geometry";
import type { DecodedImage } from "../core/image";

interface PreviewCanvasProps {
  image: DecodedImage;
  selection: GridSelection;
  expand: ExpandOptions;
  onBiasChange: (value: number) => void;
}

interface DrawMetrics {
  x: number;
  y: number;
  width: number;
  height: number;
  scale: number;
}

interface DragState {
  pointerId: number;
  startPointer: number;
  startLeadingTrim: number;
  excess: number;
  scale: number;
}

export function PreviewCanvas({
  image,
  selection,
  expand,
  onBiasChange,
}: PreviewCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const metricsRef = useRef<DrawMetrics | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const styleCacheRef = useRef<Array<{ stroke: string; halo: string | null }>>([]);
  const lastContrastRevisionRef = useRef(-1);
  const [size, setSize] = useState({ width: 640, height: 640 });
  const [contrastRevision, setContrastRevision] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const crop = effectiveCrop(image.width, image.height, expand);

  useEffect(() => {
    if (!hostRef.current) return;
    let settleTimer = 0;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(280, Math.floor(entry.contentRect.width));
      const height = Math.max(320, Math.floor(entry.contentRect.height));
      setSize({ width, height });
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(() => setContrastRevision((value) => value + 1), 160);
    });
    observer.observe(hostRef.current);
    return () => {
      observer.disconnect();
      window.clearTimeout(settleTimer);
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setContrastRevision((value) => value + 1), 120);
    return () => window.clearTimeout(timer);
  }, [selection, expand.enabled, expand.biasPercent]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = size.width;
    canvas.height = size.height;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;

    context.clearRect(0, 0, size.width, size.height);
    context.fillStyle = "#102f33";
    context.fillRect(0, 0, size.width, size.height);

    const workingWidth = crop.rect.x1 - crop.rect.x0;
    const workingHeight = crop.rect.y1 - crop.rect.y0;
    const availableWidth = Math.max(1, size.width - 40);
    const availableHeight = Math.max(1, size.height - 62);
    const scale = Math.min(availableWidth / workingWidth, availableHeight / workingHeight);
    const drawWidth = workingWidth * scale;
    const drawHeight = workingHeight * scale;
    const x = (size.width - drawWidth) / 2;
    const y = (size.height - drawHeight) / 2;
    metricsRef.current = { x, y, width: drawWidth, height: drawHeight, scale };

    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(
      image.source,
      crop.rect.x0,
      crop.rect.y0,
      workingWidth,
      workingHeight,
      x,
      y,
      drawWidth,
      drawHeight,
    );

    const geometry = buildGridGeometry(workingWidth, workingHeight, selection);
    const lines = [
      ...geometry.verticalGuides.map((guide) => ({
        x0: x + guide * scale,
        y0: y,
        x1: x + guide * scale,
        y1: y + drawHeight,
      })),
      ...geometry.horizontalGuides.map((guide) => ({
        x0: x,
        y0: y + guide * scale,
        x1: x + drawWidth,
        y1: y + guide * scale,
      })),
    ];

    if (
      styleCacheRef.current.length !== lines.length ||
      lastContrastRevisionRef.current !== contrastRevision
    ) {
      styleCacheRef.current = lines.map((line) =>
        chooseGuideStyle(sampleCanvasLine(context, line.x0, line.y0, line.x1, line.y1)),
      );
      lastContrastRevisionRef.current = contrastRevision;
    }

    lines.forEach((line, index) => {
      const style = styleCacheRef.current[index] ?? { stroke: "#0F8F84", halo: null };
      if (style.halo) {
        context.beginPath();
        context.moveTo(line.x0, line.y0);
        context.lineTo(line.x1, line.y1);
        context.strokeStyle = style.halo;
        context.lineWidth = 5;
        context.stroke();
      }
      context.beginPath();
      context.moveTo(line.x0, line.y0);
      context.lineTo(line.x1, line.y1);
      context.strokeStyle = style.stroke;
      context.lineWidth = 2;
      context.stroke();
    });

    context.strokeStyle = "rgba(255,255,255,.72)";
    context.lineWidth = 1;
    context.strokeRect(x + 0.5, y + 0.5, drawWidth - 1, drawHeight - 1);
  }, [contrastRevision, crop, image, selection, size]);

  const startDrag = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!expand.enabled || !crop.axis || !metricsRef.current) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startPointer: crop.axis === "x" ? event.clientX : event.clientY,
      startLeadingTrim: crop.leadingTrimPx,
      excess: crop.excessPx,
      scale: metricsRef.current.scale,
    };
    setIsDragging(true);
  };

  const moveDrag = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag || !crop.axis || drag.excess <= 0) return;
    const pointer = crop.axis === "x" ? event.clientX : event.clientY;
    const sourceDelta = (pointer - drag.startPointer) / drag.scale;
    const leadingTrim = Math.max(0, Math.min(drag.excess, drag.startLeadingTrim + sourceDelta));
    onBiasChange((leadingTrim / drag.excess) * 100);
  };

  const endDrag = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
      setIsDragging(false);
      setContrastRevision((value) => value + 1);
    }
  };

  const cursor = expand.enabled && crop.axis ? (isDragging ? "grabbing" : "grab") : "default";

  return (
    <div className="preview-canvas-host" ref={hostRef}>
      <canvas
        aria-label="Cut preview"
        className="preview-canvas"
        ref={canvasRef}
        style={{ cursor }}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      />
      <div className="preview-caption">
        <span>{image.width.toLocaleString()} x {image.height.toLocaleString()} px</span>
        <span>
          {crop.axis
            ? `${crop.axis === "x" ? "Horizontal" : "Vertical"} trim ${crop.biasPercent.toFixed(0)}%`
            : "Full source area"}
        </span>
      </div>
    </div>
  );
}
