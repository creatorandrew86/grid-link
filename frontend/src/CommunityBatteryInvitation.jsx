import { useEffect, useState } from 'react';
import { api } from './apiClient';
import BatteryComparison from './BatteryComparison';

export default function CommunityBatteryInvitation({ community, comparison, stale, busy, onReview }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setPreview(null); setError('');
    if (comparison) {
      api('community-battery/invitation', 'POST', { ...comparison, target_community_id: community.id })
        .then(data => { if (active) setPreview(data); })
        .catch(err => { if (active) setError(err.message); });
    }
    return () => { active = false; };
  }, [comparison, community.id]);

  return <article className="battery-invitation" aria-label={`Invitation to ${community.name}`}>
    <p className="eyebrow">COMMUNITY INVITATION</p>
    <h3>{community.name}</h3>
    <p className="muted">Battery plan: {community.battery_policy} · eligible for your meter</p>
    <p className="muted">This comparison is recalculated for {community.name}, including your demand, solar and contribution after joining.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {!preview && !error && <p role="status">{comparison ? 'Recalculating battery sizes for this invitation…' : 'Calculating your current community first…'}</p>}
    {preview && <BatteryComparison result={preview} stale={stale} compact />}
    <button className="button outline" disabled={busy || stale || !preview} onClick={onReview}>Review invitation and switch</button>
  </article>;
}
