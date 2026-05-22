import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import AboutMe from './pages/AboutMe';
import Resume from './pages/Resume';
import CoverLetter from './pages/CoverLetter';
import Education from './pages/Education';
import Certifications from './pages/Certifications';
import Skills from './pages/Skills';
import SocialMediaProfiles from './pages/SocialMediaProfiles';
import './App.css';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="about-me" element={<AboutMe />} />
        <Route path="resume" element={<Resume />} />
        <Route path="cover-letter" element={<CoverLetter />} />
        <Route path="education" element={<Education />} />
        <Route path="certifications" element={<Certifications />} />
        <Route path="skills" element={<Skills />} />
        <Route path="social-media-profiles" element={<SocialMediaProfiles />} />
      </Route>
    </Routes>
  );
}

export default App;