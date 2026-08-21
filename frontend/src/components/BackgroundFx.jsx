/**
 * Fixed decorative backdrop. The canvas carries no colour of its own — no
 * ambient glow, grid or vignette — so every trace of hue on the page comes
 * from the HUD itself. What is left is surface: the scanlines give the CRT its
 * horizontal structure, the grain gives the phosphor its texture. Both are
 * monochrome, and both stay well below the threshold where they would read as
 * a pattern rather than as a screen.
 */
function BackgroundFx() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="bg-fx__scanlines" />
      <div className="bg-fx__grain" />
    </div>
  );
}

export default BackgroundFx;
