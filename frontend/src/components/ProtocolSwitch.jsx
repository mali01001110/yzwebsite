import { Moon, Sun } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

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
  const { translate: t } = useLanguage();
  const current = isDay ? 'DAY' : 'NIGHT';
  const Icon = isDay ? Sun : Moon;
  const actionLabel = isDay ? 'Switch to night protocol' : 'Switch to day protocol';

  return (
    <button
      type="button"
      className={`protocol-switch ${isSwitching ? 'is-switching' : ''}`.trim()}
      onClick={onToggle}
      disabled={isSwitching}
      aria-label={t(actionLabel)}
      aria-live="polite"
      title={t(`Protocol: ${current}`)}
    >
      <span className="protocol-switch__glyph" aria-hidden="true">
        <Icon size={14} />
      </span>

      <span className="protocol-switch__readout">
        <span className="protocol-switch__label" aria-hidden="true">
          {t('PROTOCOL')}
        </span>
        <span className="protocol-switch__value">{t(current)}</span>
      </span>

      <span className="protocol-switch__scan" aria-hidden="true" />
    </button>
  );
}

export default ProtocolSwitch;
