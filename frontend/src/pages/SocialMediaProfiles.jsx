import { BriefcaseBusiness, Users, Music2 } from 'lucide-react';
import Section from '../components/Section';

const INTRO = `Find me online! Feel free to connect or follow me on any of the platforms listed below.`;

const PROFILES = [
  {
    name: 'LinkedIn',
    url: 'https://www.linkedin.com/in/mali01001110/',
    description: 'Connect with me professionally',
    Icon: BriefcaseBusiness,
  },
  {
    name: 'Facebook',
    url: 'https://www.facebook.com/profile.php?id=61586600751798',
    description: 'Follow my Facebook page',
    Icon: Users,
  },
  {
    name: 'TikTok',
    url: 'https://www.tiktok.com/@sometaware?is_from_webapp=1&sender_device=pc',
    description: 'Check out my TikTok videos',
    Icon: Music2,
  },
];

function SocialMediaProfiles() {
  return (
    <Section id="social" title="Social" subtitle="External channels // open links">
      <p className="prose">{INTRO}</p>

      <div className="social-grid">
        {PROFILES.map(({ name, url, description, Icon }) => (
          <a
            key={name}
            href={url}
            className="hud-panel hud-panel--cut hud-brackets social-card"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className="social-card__icon" aria-hidden="true">
              <Icon size={18} strokeWidth={1.5} />
            </span>
            <span>
              <span className="social-card__name">{name}</span>
              <span className="social-card__description">{description}</span>
            </span>
          </a>
        ))}
      </div>
    </Section>
  );
}

export default SocialMediaProfiles;
