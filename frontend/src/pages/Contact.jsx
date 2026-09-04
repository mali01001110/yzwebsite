import { useState } from 'react';
import { Send } from 'lucide-react';
import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import InfoPanel from '../components/InfoPanel';
import BrandLogo from '../components/BrandLogo';
import TickBar from '../components/TickBar';

const EMAIL_ADDRESS = 'yannzakpa@gmail.com';

// Django serves this bundle, so the API is same-origin in production; the Vite
// dev server proxies the same path to Django during development.
const CONTACT_ENDPOINT = '/api/contact/';

// Each channel is identified by the provider that actually carries it, in
// that provider's own logo: Orange for the +225 07 voice line, WhatsApp for
// the messaging number, Gmail for the address.
const CHANNELS = [
  {
    label: 'Phone',
    value: '+225 0709390845',
    href: 'tel:+2250709390845',
    brand: 'orange',
  },
  {
    label: 'WhatsApp',
    value: '+225 0709390845',
    href: 'https://wa.me/2250709390845',
    brand: 'whatsapp',
  },
  {
    label: 'Email',
    value: EMAIL_ADDRESS,
    href: `mailto:${EMAIL_ADDRESS}`,
    brand: 'gmail',
  },
];

// Everything a recruiter needs to work out whether they can reach me and
// when. Restated here rather than linked back to the About section: this is
// the panel someone is looking at when the question comes up.
const AVAILABILITY_ROWS = [
  { key: 'Based in', value: 'Abidjan, Côte d’Ivoire' },
  { key: 'Timezone', value: 'GMT (UTC+00)' },
  { key: 'Languages', value: 'French / English' },
  { key: 'Status', value: 'Open to opportunities' },
];

// Mirrors the max_length values on the ContactMessage model, so the browser
// stops oversized input before the API has to reject it.
const FIELD_LIMITS = { name: 80, email: 120, message: 2000 };

const EMPTY_FORM = { name: '', email: '', message: '' };

const FALLBACK_ERROR = 'Transmission failed. Please try again, or email me directly.';

/** Pulls a readable message out of a DRF error body (field errors or `detail`). */
function extractErrorMessage(payload) {
  if (!payload || typeof payload !== 'object') {
    return FALLBACK_ERROR;
  }

  if (typeof payload.detail === 'string') {
    return payload.detail;
  }

  const firstFieldError = Object.values(payload)
    .flat()
    .find((entry) => typeof entry === 'string');

  return firstFieldError ?? FALLBACK_ERROR;
}

function Contact() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [status, setStatus] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const isSending = status === 'sending';

  // Success and failure read as the same grey caption otherwise, which leaves
  // the outcome of a submission legible only by reading the sentence.
  const noteClassName = [
    'transmit__note',
    status === 'success' ? 'transmit__note--ok' : '',
    status === 'error' ? 'transmit__note--error' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const updateField = (field) => (event) => {
    const { value } = event.target;
    setForm((current) => ({
      ...current,
      [field]: value.slice(0, FIELD_LIMITS[field]),
    }));
    if (status !== 'idle') {
      setStatus('idle');
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus('sending');
    setErrorMessage('');

    try {
      const response = await fetch(CONTACT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          email: form.email.trim(),
          message: form.message.trim(),
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        setErrorMessage(extractErrorMessage(payload));
        setStatus('error');
        return;
      }

      setForm(EMPTY_FORM);
      setStatus('success');
    } catch {
      setErrorMessage(FALLBACK_ERROR);
      setStatus('error');
    }
  };

  return (
    <Section id="contact" title="Contact" subtitle="Open channel // transmit data packet">
      <div className="contact">
        <HudWindow title="CHANNELS.SYS" tag="DIRECT" className="contact__channels-window">
          <div className="channel-options">
            {CHANNELS.map(({ label, value, href, brand }) => (
              <a
                key={label}
                className="channel-option"
                href={href}
                {...(href.startsWith('http')
                  ? { target: '_blank', rel: 'noopener noreferrer' }
                  : {})}
              >
                <span className="channel-option__body">
                  <span className="channel-option__label">&gt; {label}</span>
                  <span className="channel-option__value">{value}</span>
                </span>
                <span className="channel-option__box" aria-hidden="true">
                  <BrandLogo name={brand} size={24} />
                </span>
              </a>
            ))}
          </div>

          <div className="contact__availability">
            <InfoPanel title="Availability" rows={AVAILABILITY_ROWS} />
          </div>

          <TickBar value={100} label="Channels open" showValue={false} />
        </HudWindow>

        <HudWindow title="TRANSMIT.EXE" tag="SECURE" className="contact__form-window">
          <form className="transmit" onSubmit={handleSubmit}>
            <div className="transmit__row">
              <label className="hud-field">
                <span className="hud-label hud-label--muted">Name</span>
                <input
                  className="hud-field__input"
                  type="text"
                  required
                  maxLength={FIELD_LIMITS.name}
                  value={form.name}
                  onChange={updateField('name')}
                  disabled={isSending}
                  placeholder="Your name"
                />
              </label>

              <label className="hud-field">
                <span className="hud-label hud-label--muted">Email</span>
                <input
                  className="hud-field__input"
                  type="email"
                  required
                  maxLength={FIELD_LIMITS.email}
                  value={form.email}
                  onChange={updateField('email')}
                  disabled={isSending}
                  placeholder="you@domain.com"
                />
              </label>
            </div>

            <label className="hud-field hud-field--grow">
              <span className="hud-label hud-label--muted">Message</span>
              <textarea
                className="hud-field__textarea"
                required
                maxLength={FIELD_LIMITS.message}
                value={form.message}
                onChange={updateField('message')}
                disabled={isSending}
                placeholder="Type your message…"
              />
            </label>

            <p className="transmit__prompt">Initiate transmission?</p>

            <button type="submit" className="execute-button" disabled={isSending}>
              <Send size={18} aria-hidden="true" />
              {isSending ? '> TRANSMITTING…' : '> EXECUTE'}
            </button>

            <p className={noteClassName} role="status" aria-live="polite">
              {status === 'success' && 'Transmission received. I will get back to you shortly.'}
              {status === 'error' && errorMessage}
              {(status === 'idle' || isSending) &&
                'Your message is delivered straight to my inbox.'}
            </p>
          </form>
        </HudWindow>
      </div>
    </Section>
  );
}

export default Contact;
