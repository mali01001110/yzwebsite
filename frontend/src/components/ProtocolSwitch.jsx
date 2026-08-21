import { Moon, Sun } from 'lucide-react';

/**
 * Day/night control, styled as a HUD protocol selector rather than a generic
 * theme toggle — angular frame, notched corner, scanning light bar and a
 * status readout, matching the rest of the interface.
 *
 * The label states the *current* protocol rather than the one a press would
 * switch to. A control that names the thing it is not is a recurring source of
 * confusion in theme switchers; `aria-label` carries the action instead, which
 * is where a screen reader expects to find it.
 */
function ProtocolSwitch({ isDay, isSwitching, onToggle }) {
  const current = isDay ? 'DAY' : 'NIGHT';
  const next = isDay ? 'night' : 'day';
  const Icon = isDay ? Sun : Moon;

  return (
    <button
      type="button"
      className={`protocol-switch ${isSwitching ? 'is-switching' : ''}`.trim()}
      onClick={onToggle}
      disabled={isSwitching}
      aria-label={`Switch to ${next} protocol`}
      aria-live="polite"
      title={`Protocol: ${current}`}
    >
      <span className="protocol-switch__glyph" aria-hidden="true">
        <Icon size={14} />
      </span>

      <span className="protocol-switch__readout">
        <span className="protocol-switch__label" aria-hidden="true">
          PROTOCOL
        </span>
        <span className="protocol-switch__value">{current}</span>
      </span>

      <span className="protocol-switch__scan" aria-hidden="true" />
    </button>
  );
}

export default ProtocolSwitch;
