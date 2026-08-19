import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import ConsentBanner from './components/ConsentBanner';
import { useAnalytics } from './hooks/useAnalytics';
import './App.css';

function App() {
  // Loads the first-party beacon and reports route changes. Renders nothing.
  useAnalytics();

  return (
    <>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
        </Route>
      </Routes>
      {/* Mounted but switched off, mirroring ANALYTICS['REQUIRE_CONSENT'],
          which defaults to False for this site. Flip both together to start
          gating beacon data on consent. */}
      <ConsentBanner enabled={false} />
    </>
  );
}

export default App;
