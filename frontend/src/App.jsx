import { useEffect, useState } from 'react';
import { api } from './apiClient';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import SignUp from './pages/SignUp';
import Account from './pages/Account';
import Terms from './pages/Terms';
import Privacy from './pages/Privacy';

export default function App() {
  const [page, setPage] = useState(() => {
    const hash = window.location.hash.replace('#', '');
    if (['signup', 'login'].includes(hash)) return 'signup';
    if (hash === 'account') return 'account';
    if (hash === 'terms') return 'terms';
    if (hash === 'privacy') return 'privacy';
    return 'home';
  });

  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sessionToken, setSessionToken] = useState(() => {
    try {
      return localStorage.getItem('gridlink-token') || '';
    } catch {
      return '';
    }
  });

  const navigate = (target) => {
    setPage(target);
    window.location.hash = target === 'home' ? '' : target;
  };

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (['signup', 'login'].includes(hash)) setPage('signup');
      else if (hash === 'account') setPage('account');
      else if (hash === 'terms') setPage('terms');
      else if (hash === 'privacy') setPage('privacy');
      else setPage('home');
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  async function refresh() {
    setBusy(true);
    setError('');
    try {
      const result = await api('clearing-summary');
      setSummary(result);
    } catch (err) {
      if (err.status === 401) {
        localStorage.removeItem('gridlink-token');
        setSessionToken('');
        setProfile(null);
        setSummary(null);
      }
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (busy) return;
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [busy]);

  const [profile, setProfile] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (sessionToken) {
      api('me').then((member) => {
        if (!cancelled) setProfile(member);
      }).catch(() => {
        if (!cancelled) setProfile(null);
      });
    } else {
      setProfile(null);
    }
    return () => { cancelled = true; };
  }, [sessionToken]);

  const activeMember = summary?.participants?.find(
    (m) => m.id === profile?.id
  );

  const currentMember = activeMember ? { ...activeMember, ...profile } : profile;

  const handleJoined = (newMember) => {
    setProfile(newMember);
    setSummary(null);
    try {
      setSessionToken(localStorage.getItem('gridlink-token') || '');
      localStorage.setItem('gridlink-member', newMember.id);
      if (newMember.email) localStorage.setItem('gridlink-email', newMember.email);
    } catch {}
    refresh();
  };

  const handleLogout = async () => {
    try { await api('logout', 'POST'); } catch {}
    try {
      localStorage.removeItem('gridlink-member');
      localStorage.removeItem('gridlink-token');
      localStorage.removeItem('gridlink-email');
    } catch {}
    setSessionToken('');
    setProfile(null);
    setSummary(null);
    refresh();
    navigate('home');
  };

  return (
    <>
      <Header
        page={page}
        onNavigate={navigate}
        activeMember={currentMember}
        busy={busy}
      />

      {page === 'home' && (
        <Home
          summary={summary}
          refresh={refresh}
          busy={busy}
          error={error}
          setError={setError}
          notice={notice}
          setNotice={setNotice}
          member={currentMember}
          onNavigate={navigate}
        />
      )}

      {page === 'signup' && (
        <SignUp
          onJoined={handleJoined}
          onNavigate={navigate}
        />
      )}

      {page === 'account' && (
        <Account
          member={currentMember}
          summary={summary}
          loading={busy || !summary}
          refresh={refresh}
          busy={busy}
          onNavigate={navigate}
          onLogout={handleLogout}
        />
      )}

      {page === 'terms' && (
        <Terms onNavigate={navigate} />
      )}

      {page === 'privacy' && (
        <Privacy onNavigate={navigate} />
      )}

      <Footer
        onNavigate={navigate}
        storage={summary?.storage}
      />
    </>
  );
}
