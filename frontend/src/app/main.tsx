import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { reloadOnce } from '@/shared/lib/reload';

import { App } from './App';

// Vite reports a page file it could not load after a deploy. Reload once to get the new files; if that already
// happened, let the error reach the route's error page.
window.addEventListener('vite:preloadError', (event) => {
  if (reloadOnce()) event.preventDefault();
});

const root = document.getElementById('root');
if (!root) throw new Error('Root element missing');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
