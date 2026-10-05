import { useEffect, useState } from 'react';
import { api } from './apiClient';
import BatteryComparison from './BatteryComparison';
import CommunityBatteryInvitation from './CommunityBatteryInvitation';

export default function CommunityBatteryPlan({ memberId, onSwitched }) {
  const [context, setContext] = useState(null);
  const [destination, setDestination] = useState(null);
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api('community-battery').then(data => { if (active) setContext(data); })
      .catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [memberId]);

  useEffect(() => { if (context?.community.id) compare(); }, [context?.community.id]);

  const communityDisagrees = context && (context.community.battery_policy === 'declined' ||
    (context.community.battery_policy !== 'approved' && context.answered_count > context.interested_count));

  async function compare() {
    setError(''); setNotice(''); setDestination(null); setBusy(true);
    try {
      const data = await api('community-battery/analysis', 'POST', {});
      setResult(data); setComparison({});
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveInterest(interested) {
    setBusy(true); setError(''); setNotice('');
    try {
      await api('community-battery/interest', 'PUT', { interested });
      setContext(await api('community-battery'));
      setNotice('Your preference is saved. No payment has been committed.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function acceptSwitch(target_community_id) {
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await api('community-battery/switch', 'POST', { target_community_id });
      onSwitched(data.user);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="community-battery-plan" aria-labelledby="community-battery-title">
    <p className="eyebrow">SHARED STORAGE / COMMUNITY INVESTMENT</p>
    <h2 id="community-battery-title">A battery for {context?.community.name || 'your current community'}.</h2>
    <p className="muted">Compare whole-community savings and two ways to share the cost. Member records stay private.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {!context ? <p className="muted">{error ? 'Planning is unavailable until the connection or database setup is fixed.' : 'Loading your community…'}</p> : <>
      <div className="community-battery-status">
        <div><span className="eyebrow">YOUR COMMUNITY</span><strong>{context.community.name}</strong><p className="muted">Battery plan: {context.community.battery_policy}</p></div>
        <div><span className="eyebrow">{context.community.is_demo ? 'DEMO REPLAY HISTORY' : 'MEASURED HISTORY'}</span><strong>{context.coverage.complete_days} complete days</strong><p className="muted">{context.coverage.incomplete_days} incomplete days excluded. ROI needs 30 complete days.</p></div>
        <div><span className="eyebrow">SHARED FUNDING</span><strong>{context.member_count} members</strong><p className="muted">{context.interested_count} interested · {context.answered_count} answered</p></div>
      </div>

      <p className="muted">Measurements, contract tariffs, battery quotes and connection limits are supplied by the system and your community operator. You do not need to enter analysis parameters.</p>
      <button className="button outline" disabled={busy} onClick={compare}>{busy ? 'Updating analysis...' : 'Refresh analysis'}</button>
      {context.community.is_demo && <p><a href="/demo/index.html" target="_blank" rel="noreferrer">Open pitch cases and algorithm charts</a></p>}
      {result && <BatteryComparison result={result} />}

      <div className="battery-community-choice">
        <h3>Would you fund a shared battery?</h3>
        <p className="muted">Your current preference: {context.your_interest == null ? 'Not answered' : context.your_interest ? 'Interested' : 'Not interested'}. The community must agree on the purchase before anyone pays.</p>
        <div className="battery-preference-actions"><button className="button primary" disabled={busy} onClick={() => saveInterest(true)}>I’m interested</button><button className="button outline" disabled={busy} onClick={() => saveInterest(false)}>Not interested</button></div>
        {context.your_interest && communityDisagrees && <>
          <h3>Find a community planning shared storage</h3>
          <p className="muted">These communities want shared storage and have opened admissions in your network zone. Review a suggestion, then choose whether to switch. Your home and meter stay where they are; joining does not commit a payment.</p>
          {context.candidates.length ? context.candidates.map(c => <CommunityBatteryInvitation key={c.id} community={c} comparison={comparison} busy={busy} onReview={() => setDestination(c)} />) : <p className="muted">No eligible community is accepting members yet. Your operator can review communities and your meter’s eligibility.</p>}
          {destination && <div className="planning-assumption" role="region" aria-label="Review community switch"><h3>Switch to {destination.name}?</h3><p>You will leave {context.community.name} and join {destination.name}, which is planning shared storage. The server checks admissions and meter eligibility again before moving your membership.</p><div className="battery-preference-actions"><button className="button primary" disabled={busy} onClick={() => acceptSwitch(destination.id)}>Accept and switch community</button><button className="button outline" disabled={busy} onClick={() => setDestination(null)}>Stay in my community</button></div></div>}
        </>}
      </div>
    </>}
  </section>;
}
