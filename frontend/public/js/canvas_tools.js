/**
 * Canvas Tools: Telestrator (Live drawing) and Virtual Laser Pointer
 * Uses normalized (0.0 to 1.0) coordinates for resolution independence.
 */

class RemoteCanvasTools {
  constructor(canvasElement, onStrokeEmit, onPointerEmit) {
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext("2d");
    this.onStrokeEmit = onStrokeEmit;
    this.onPointerEmit = onPointerEmit;

    this.isDrawing = false;
    this.toolMode = "pointer"; // 'pointer' or 'pen'
    this.strokeColor = "#ef4444";
    this.lineWidth = 3;

    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());
    this.bindEvents();
  }

  resizeCanvas() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
  }

  setMode(mode) {
    this.toolMode = mode;
    this.canvas.style.cursor = mode === "pen" ? "crosshair" : "default";
  }

  bindEvents() {
    this.canvas.addEventListener("mousemove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const normX = (e.clientX - rect.left) / rect.width;
      const normY = (e.clientY - rect.top) / rect.height;

      if (this.onPointerEmit) {
        this.onPointerEmit({ x: normX, y: normY, active: true });
      }

      if (this.isDrawing && this.toolMode === "pen") {
        this.drawLine(this.lastX, this.lastY, normX, normY, this.strokeColor, this.lineWidth);
        if (this.onStrokeEmit) {
          this.onStrokeEmit({
            type: "draw_line",
            x0: this.lastX,
            y0: this.lastY,
            x1: normX,
            y1: normY,
            color: this.strokeColor,
            width: this.lineWidth
          });
        }
        this.lastX = normX;
        this.lastY = normY;
      }
    });

    this.canvas.addEventListener("mousedown", (e) => {
      if (this.toolMode === "pen") {
        this.isDrawing = true;
        const rect = this.canvas.getBoundingClientRect();
        this.lastX = (e.clientX - rect.left) / rect.width;
        this.lastY = (e.clientY - rect.top) / rect.height;
      }
    });

    window.addEventListener("mouseup", () => {
      this.isDrawing = false;
    });

    this.canvas.addEventListener("mouseleave", () => {
      this.isDrawing = false;
      if (this.onPointerEmit) {
        this.onPointerEmit({ active: false });
      }
    });
  }

  drawLine(x0, y0, x1, y1, color, width) {
    const w = this.canvas.width;
    const h = this.canvas.height;

    this.ctx.beginPath();
    this.ctx.moveTo(x0 * w, y0 * h);
    this.ctx.lineTo(x1 * w, y1 * h);
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = width;
    this.ctx.lineCap = "round";
    this.ctx.stroke();
  }

  clear() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}

window.RemoteCanvasTools = RemoteCanvasTools;

