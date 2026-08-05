/**
 * Angular HUD control with a scanning light bar. Renders an anchor when `href`
 * is supplied, otherwise a native button.
 */
function HudButton({
  href,
  variant = 'solid',
  block = false,
  className = '',
  children,
  ...rest
}) {
  const classes = [
    'hud-button',
    variant === 'ghost' ? 'hud-button--ghost' : '',
    block ? 'hud-button--block' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if (href) {
    const isExternal = href.startsWith('http');

    return (
      <a
        href={href}
        className={classes}
        {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
        {...rest}
      >
        {children}
      </a>
    );
  }

  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}

export default HudButton;
