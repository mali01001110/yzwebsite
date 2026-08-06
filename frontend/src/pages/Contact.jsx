import { useState } from 'react';
import { Phone, MessageCircle, Mail, Send } from 'lucide-react';
import Section from '../components/Section';
import HudButton from '../components/HudButton';

const EMAIL_ADDRESS = 'yannzakpa@gmail.com';

// Django serves this bundle, so the API is same-origin in production; the Vite
// dev server proxies the same path to Django during development.
const CONTACT_ENDPOINT = '/api/contact/';

const CHANNELS = [
  {
    label: 'Phone',
    value: '+225 0709390845',
    href: 'tel:+2250709390845',
    Icon: Phone,
  },
  {
    label: 'WhatsApp',
    value: '+225 0778704523',
    href: 'https://wa.me/2250778704523',
    Icon: MessageCircle,
  },
  {
    label: 'Email',
    value: EMAIL_ADDRESS,
    href: `mailto:${EMAIL_ADDRESS}`,
    Icon: Mail,
  },
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
        <div className="contact__channels">
          {CHANNELS.map(({ label, value, href, Icon }) => (
            <a
              key={label}
              href={href}
              className="contact__channel"
              {...(href.startsWith('http')
                ? { target: '_blank', rel: 'noopener noreferrer' }
                : {})}
            >
              <Icon size={20} strokeWidth={1.5} className="contact__channel-icon" />
              <span>
                <span className="contact__channel-label">{label}</span>
                <span className="contact__channel-value">{value}</span>
              </span>
            </a>
          ))}
        </div>

        <form className="hud-panel hud-panel--cut hud-brackets contact__form" onSubmit={handleSubmit}>
          <span className="hud-label">New transmission</span>

          <div className="contact__form-row">
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

          <label className="hud-field">
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

          <HudButton type="submit" block disabled={isSending}>
            <Send size={15} aria-hidden="true" />
            {isSending ? 'Transmitting…' : 'Transmit data packet'}
          </HudButton>

          <p className="contact__form-note" role="status" aria-live="polite">
            {status === 'success' && 'Transmission received. I will get back to you shortly.'}
            {status === 'error' && errorMessage}
            {(status === 'idle' || isSending) &&
              'Your message is delivered straight to my inbox.'}
          </p>
        </form>
      </div>
    </Section>
  );
}

export default Contact;
