/**
 * Fixed decorative backdrop: perspective grid, navy depth glow, CRT scanlines,
 * a slow vertical scan sweep and an edge vignette. Purely presentational.
 */
function BackgroundFx() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="bg-fx__glow" />
      <div className="bg-fx__grid" />
      <div className="bg-fx__scanlines" />
      <div className="bg-fx__sweep" />
      <div className="bg-fx__vignette" />
    </div>
  );
}

export default BackgroundFx;
