/**
 * Fixed decorative backdrop. The canvas is pure black by design — no ambient
 * glow, grid or vignette — so every trace of colour on the page comes from the
 * HUD itself. Only the CRT scanline texture survives.
 */
function BackgroundFx() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="bg-fx__scanlines" />
    </div>
  );
}

export default BackgroundFx;
