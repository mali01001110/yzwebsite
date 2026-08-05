import { useState } from 'react';
import { Download } from 'lucide-react';
import Section from '../components/Section';
import DocumentThumb from '../components/DocumentThumb';
import ImageLightbox from '../components/ImageLightbox';
import HudButton from '../components/HudButton';
import resumeImage from '../assets/resume.jpg';

const RESUME_ALT = 'Scanned image of resume showing work experience and skills';

function Resume() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Section id="resume" title="Resume" subtitle="Full dossier // education, certs, experience">
      <div className="resume">
        <DocumentThumb
          src={resumeImage}
          alt={RESUME_ALT}
          onOpen={() => setIsOpen(true)}
          hint="Open dossier"
        />

        <div className="hud-panel hud-panel--cut hud-brackets resume__body">
          <span className="hud-label">Record.dossier</span>
          <h3 className="resume__title">Professional and Educational Background</h3>
          <p>
            Open the resume image to view the complete education, certifications, and
            professional experience details.
          </p>
          <div>
            <HudButton onClick={() => setIsOpen(true)}>
              <Download size={15} aria-hidden="true" />
              Open full scan
            </HudButton>
          </div>
        </div>
      </div>

      {isOpen && (
        <ImageLightbox src={resumeImage} alt={RESUME_ALT} onClose={() => setIsOpen(false)} />
      )}
    </Section>
  );
}

export default Resume;
