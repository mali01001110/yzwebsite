import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import DataRow from '../components/DataRow';
import StaggerGrid from '../components/StaggerGrid';
import { SOCIAL_URLS } from '../data/social';

const INTRO = `Find me online! Feel free to connect or follow me on any of the platforms listed below.`;

// Same marks the footer uses, so a visitor meets one logo per platform
// wherever it appears on the page.
const PROFILES = [
  {
    name: 'LinkedIn',
    url: SOCIAL_URLS.linkedin,
    description: 'Connect with me professionally',
    brand: 'linkedin',
  },
  {
    name: 'Facebook',
    url: SOCIAL_URLS.facebook,
    description: 'Follow my Facebook page',
    brand: 'facebook',
  },
  {
    name: 'TikTok',
    url: SOCIAL_URLS.tiktok,
    description: 'Check out my TikTok videos',
    brand: 'tiktok',
  },
];

function SocialMediaProfiles() {
  return (
    <Section id="social" title="Social" subtitle="External channels // open links">
      <p className="prose">{INTRO}</p>

      <HudWindow
        title="CHANNELS.NET"
        tag={`${String(PROFILES.length).padStart(2, '0')} LINKS`}
      >
        <StaggerGrid className="channels" threshold={0.05}>
          {PROFILES.map(({ name, url, description, brand }, index) => (
            <DataRow
              key={name}
              index={String(index + 1).padStart(2, '0')}
              brand={brand}
              label={name}
              meta={description}
              actionLabel="OPEN"
              glyph="↗"
              href={url}
            />
          ))}
        </StaggerGrid>
      </HudWindow>
    </Section>
  );
}

export default SocialMediaProfiles;
