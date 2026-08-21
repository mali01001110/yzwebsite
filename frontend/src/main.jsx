import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { LucideProvider } from 'lucide-react';
import './index.css';
import App from './App.jsx';

/**
 * One stroke weight for every icon on the site.
 *
 * Lucide ships at 2, which is heavy next to hairline HUD frames, and the call
 * sites had drifted to three different values. Setting it here rather than per
 * icon means a new icon cannot arrive at the wrong weight. Size stays a prop —
 * it genuinely varies by context.
 */
const ICON_STROKE_WIDTH = 1.5;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <LucideProvider strokeWidth={ICON_STROKE_WIDTH}>
        <App />
      </LucideProvider>
    </BrowserRouter>
  </StrictMode>,
);
