import { BriefcaseBusiness, Users, Music2 } from 'lucide-react';
import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import DataRow from '../components/DataRow';
import StaggerGrid from '../components/StaggerGrid';

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

      <HudWindow
        title="CHANNELS.NET"
        tag={`${String(PROFILES.length).padStart(2, '0')} LINKS`}
      >
        <StaggerGrid className="channels" threshold={0.05}>
          {PROFILES.map(({ name, url, description, Icon }, index) => (
            <DataRow
              key={name}
              index={String(index + 1).padStart(2, '0')}
              Icon={Icon}
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
