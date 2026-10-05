import { Arrow } from '../pages/Home';

function UserIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="7" r="4" />
      <path d="M4 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2" />
    </svg>
  );
}

export default function Header({ page, onNavigate, activeMember, busy }) {
  return (
    <header className="site-header">
      <a className="brand" href="#home" onClick={(e) => { e.preventDefault(); onNavigate('home'); }} aria-label="GridLink home">
        <span className="brand-mark">GL</span>
        <span>gridlink<span className="brand-period">.</span></span>
      </a>

      <nav aria-label="Main navigation">
        <button
          className="text-button"
          onClick={() => onNavigate('home')}
          style={{ color: page === 'home' ? 'var(--white)' : 'var(--muted)', padding: '8px 12px' }}
        >
          Overview
        </button>
        <a
          href={activeMember ? '#account' : '#community'}
          onClick={(e) => {
            if (activeMember) {
              e.preventDefault();
              onNavigate('account');
            } else if (page !== 'home') {
              onNavigate('home');
            }
          }}
        >
          Community
        </a>
        <a
          href="#pricing"
          onClick={() => {
            if (page !== 'home') onNavigate('home');
          }}
        >
          Data sources
        </a>
        <a
          href="#account"
          onClick={(e) => { e.preventDefault(); onNavigate(activeMember ? 'account' : 'signup'); }}
        >
          Battery analysis
        </a>
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          className="button primary"
          onClick={() => onNavigate('signup')}
          disabled={busy}
        >
          {activeMember ? 'Add Meter' : 'Join community'}
          <Arrow diagonal />
        </button>

        <button
          className="icon-button"
          onClick={() => onNavigate('account')}
          aria-label="Account details"
          title={activeMember ? `Account: ${activeMember.name}` : 'Account'}
          style={{
            width: '42px',
            height: '42px',
            border: '1px solid var(--line)',
            borderRadius: '6px',
            background: page === 'account' ? 'var(--yellow)' : 'var(--carbon)',
            color: page === 'account' ? '#000' : 'var(--white)',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
            transition: 'background .15s',
          }}
        >
          <UserIcon />
        </button>
      </div>
    </header>
  );
}
