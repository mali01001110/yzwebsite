import { useState } from 'react';
import { Download } from 'lucide-react';
import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import DocumentThumb from '../components/DocumentThumb';
import ImageLightbox from '../components/ImageLightbox';
import InfoPanel from '../components/InfoPanel';
import resumeImage from '../assets/resume.jpg';

const RESUME_ALT = 'Scanned image of resume showing work experience and skills';

const DOSSIER_ROWS = [
  { key: 'Type', value: 'Full dossier' },
  { key: 'Contains', value: 'Education / Certs / Experience' },
  { key: 'Format', value: 'Image scan' },
  { key: 'Access', value: 'Public' },
];

function Resume() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Section id="resume" title="Resume" subtitle="Full dossier // education, certs, experience">
      <HudWindow title="DOSSIER.SCAN" tag="ACCESS GRANTED">
        <div className="dossier">
          <div className="dossier__viewport">
            <DocumentThumb
              src={resumeImage}
              alt={RESUME_ALT}
              onOpen={() => setIsOpen(true)}
              hint="Open dossier"
            />
          </div>

          <div className="dossier__side">
            <InfoPanel title="Record" rows={DOSSIER_ROWS} />

            <p className="dossier__note">
              Open the resume scan to view the complete education, certifications and
              professional experience details.
            </p>

            <button
              type="button"
              className="execute-button"
              onClick={() => setIsOpen(true)}
            >
              <Download size={18} aria-hidden="true" />
              &gt; EXECUTE
            </button>
          </div>
        </div>
      </HudWindow>

      {isOpen && (
        <ImageLightbox src={resumeImage} alt={RESUME_ALT} onClose={() => setIsOpen(false)} />
      )}
    </Section>
  );
}

export default Resume;
