import { Route, Routes, useLocation } from 'react-router-dom';
import NavBar from './components/NavBar.jsx';
import Footer from './components/Footer.jsx';
import ScrollManager from './components/ScrollManager.jsx';
import HomePage from './pages/HomePage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';

export default function App() {
  const { pathname } = useLocation();

  return (
    <div className="app-shell flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-16 focus:top-8 focus:z-[60] focus:rounded-pill focus:bg-ink focus:px-16 focus:py-8 focus:text-caption focus:text-paper"
      >
        Skip to content
      </a>
      <ScrollManager />
      <NavBar />
      <main id="main" className="flex-1">
        {/* Keyed on the path so each route plays one entrance, not per-element effects. */}
        <div key={pathname} className="page-enter">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </div>
      </main>
      <Footer />
    </div>
  );
}
