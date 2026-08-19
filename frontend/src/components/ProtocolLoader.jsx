/**
 * The reboot sequence shown while the protocol switches.
 *
 * Purpose beyond decoration: swapping a whole palette repaints every surface
 * at once, which reads as a flicker. This covers the repaint with something
 * deliberate, so the change looks like the interface doing its job rather than
 * the page glitching.
 *
 * Rendered only while a switch is in flight. `aria-hidden` because the switch
 * button already announces the change through `aria-live` — announcing it
 * twice is noise.
 */
function ProtocolLoader({ isSwitching, target }) {
  if (!isSwitching || !target) return null;

  return (
    <div className="protocol-loader" aria-hidden="true">
      <div className="protocol-loader__frame">
        <div className="protocol-loader__head">
          <span className="protocol-loader__code">SYS.RECALIBRATE</span>
          <span className="protocol-loader__target">{target.toUpperCase()}</span>
        </div>

        <div className="protocol-loader__track">
          <div className="protocol-loader__fill" />
        </div>

        <div className="protocol-loader__ticks" aria-hidden="true">
          {Array.from({ length: 32 }, (_, index) => (
            <span key={index} className="protocol-loader__tick" />
          ))}
        </div>

        <p className="protocol-loader__log">
          &gt; REMAPPING COLOR CHANNELS<span className="protocol-loader__caret" />
        </p>
      </div>

      <div className="hazard-bar" />
    </div>
  );
}

export default ProtocolLoader;
