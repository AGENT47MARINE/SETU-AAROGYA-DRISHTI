import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';
import { Activity, AlertTriangle, RefreshCw, Bell, ClipboardCheck, FlaskConical } from 'lucide-react';
import L from 'leaflet';

import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';
const API_KEY = import.meta.env.VITE_SETU_API_KEY || '';
const BASE_POLL_MS = 5000;
const MAX_BACKOFF_MS = 60000;

function App() {
  const [signals, setSignals] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ total_signals: 0, entity_breakdown: [] });
  const [advanced, setAdvanced] = useState({ summary: { adr_signals: 0, temporal_spikes: 0 }, alerts: [] });
  const [triageQueue, setTriageQueue] = useState([]);
  const [decisionBusy, setDecisionBusy] = useState({});
  const [decisionMessage, setDecisionMessage] = useState('');
  const [error, setError] = useState('');

  const pollTimeoutRef = useRef(null);
  const consecutive429Ref = useRef(0);
  const fetchInFlightRef = useRef(false);
  const isMountedRef = useRef(false);

  const authHeaders = API_KEY ? { 'x-api-key': API_KEY } : {};

  const fetchData = useCallback(async () => {
    if (fetchInFlightRef.current) {
      return { ok: false, retryDelay: BASE_POLL_MS };
    }

    fetchInFlightRef.current = true;
    try {
      const [signalsRes, statsRes, hotspotsRes, alertsRes, advancedRes, triageRes] = await Promise.all([
        axios.get(`${API_BASE}/signals`, { headers: authHeaders }),
        axios.get(`${API_BASE}/stats`, { headers: authHeaders }),
        axios.get(`${API_BASE}/hotspots`, { headers: authHeaders }),
        axios.get(`${API_BASE}/alerts`, { headers: authHeaders }),
        axios.get(`${API_BASE}/stats/advanced`, { headers: authHeaders }),
        axios.get(`${API_BASE}/triage/queue`, { headers: authHeaders })
      ]);

      setSignals(signalsRes.data);
      setStats(statsRes.data);
      setHotspots(hotspotsRes.data);
      setAlerts(alertsRes.data);
      setAdvanced(advancedRes.data || { summary: { adr_signals: 0, temporal_spikes: 0 }, alerts: [] });
      setTriageQueue(triageRes.data || []);
      consecutive429Ref.current = 0;
      setError('');
      return { ok: true, retryDelay: BASE_POLL_MS };
    } catch (err) {
      console.error('Fetch error:', err);
      const status = err?.response?.status;
      if (status === 429) {
        consecutive429Ref.current += 1;
        const retryDelay = Math.min(BASE_POLL_MS * (2 ** consecutive429Ref.current), MAX_BACKOFF_MS);
        setError(`Rate limited by API (429). Retrying in ${Math.round(retryDelay / 1000)}s.`);
        return { ok: false, retryDelay };
      }

      setError('Live fetch failed. Check API key or backend health.');
      return { ok: false, retryDelay: BASE_POLL_MS };
    } finally {
      fetchInFlightRef.current = false;
    }
  }, [authHeaders]);

  const clearPollTimer = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  const scheduleNextPoll = useCallback((delayMs) => {
    if (!isMountedRef.current || document.visibilityState !== 'visible') {
      return;
    }

    clearPollTimer();
    pollTimeoutRef.current = setTimeout(async () => {
      const result = await fetchData();
      scheduleNextPoll(result.retryDelay);
    }, delayMs);
  }, [clearPollTimer, fetchData]);

  const submitDecision = async (alertId, decision) => {
    setDecisionBusy((prev) => ({ ...prev, [alertId]: true }));
    setDecisionMessage('');
    try {
      await axios.post(
        `${API_BASE}/triage/${alertId}/decision`,
        {
          decision,
          reviewer: 'dashboard_reviewer',
          notes: `Decision from dashboard: ${decision}`
        },
        { headers: authHeaders }
      );
      setDecisionMessage(`Decision submitted: ${decision}`);
      const result = await fetchData();
      scheduleNextPoll(result.retryDelay);
    } catch (err) {
      console.error('Decision error:', err);
      setDecisionMessage('Failed to submit decision.');
    } finally {
      setDecisionBusy((prev) => ({ ...prev, [alertId]: false }));
    }
  };

  useEffect(() => {
    isMountedRef.current = true;

    const startPolling = async () => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      const result = await fetchData();
      scheduleNextPoll(result.retryDelay);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        clearPollTimer();
        return;
      }
      startPolling();
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      clearPollTimer();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [clearPollTimer, fetchData, scheduleNextPoll]);

  return (
    <div className="dashboard-container">
      <header className="topbar">
        <div className="logo">SETU AAROGYA DRISHTI</div>
        <div className="topbar-actions">
          <div className="kpi-pill">
            <Activity size={16} />
            {stats.total_signals} SIGNALS DETECTED
          </div>
          <button
            className="icon-button"
            onClick={async () => {
              const result = await fetchData();
              scheduleNextPoll(result.retryDelay);
            }}
            aria-label="Refresh dashboard"
          >
            <RefreshCw size={20} />
          </button>
        </div>
      </header>

      <div className="sidebar">
        {error && (
          <div className="card danger-card">
            <strong>Connection Warning</strong>
            <div style={{ fontSize: '0.85rem' }}>{error}</div>
          </div>
        )}

        <div className="card stats-card">
          <h3 className="section-title">
            <FlaskConical size={18} />
            Advanced Stats
          </h3>
          <div className="compact-row">
            <span>ADR Signals</span>
            <strong>{advanced.summary?.adr_signals || 0}</strong>
          </div>
          <div className="compact-row">
            <span>Temporal Spikes</span>
            <strong>{advanced.summary?.temporal_spikes || 0}</strong>
          </div>
        </div>

        <div className="section-block">
          <h3 className="section-title">
            <ClipboardCheck size={18} />
            Triage Queue
          </h3>
          {decisionMessage && <div className="decision-message">{decisionMessage}</div>}
          <div className="triage-list">
            {triageQueue.length === 0 && <div className="signal-meta">No pending triage items.</div>}
            {triageQueue.slice(0, 6).map((item) => (
              <div key={item.id} className="card triage-card">
                <div className="triage-headline">
                  <strong>{item.alert_type}</strong> {' '}•{' '} {item.severity}
                </div>
                <div className="signal-meta">{new Date(item.created_at).toLocaleString()}</div>
                <div className="triage-actions">
                  <button disabled={!!decisionBusy[item.id]} onClick={() => submitDecision(item.id, 'CONFIRMED')}>Confirm</button>
                  <button disabled={!!decisionBusy[item.id]} onClick={() => submitDecision(item.id, 'MORE_DATA')}>More Data</button>
                  <button disabled={!!decisionBusy[item.id]} onClick={() => submitDecision(item.id, 'REJECTED')}>Reject</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {alerts.length > 0 && (
          <div className="section-block">
            <h3 className="section-title danger-title">
              <Bell size={18} />
              Active Alerts
            </h3>
            {alerts.map((alert, i) => (
              <div key={i} className="card alert-card">
                <strong style={{ color: 'var(--danger)' }}>{alert.type}</strong>
                <div style={{ fontSize: '0.8rem' }}>{alert.count} cases of {alert.entity} detected in District {alert.district_id}</div>
              </div>
            ))}
          </div>
        )}

        <h3 className="section-title">
          <AlertTriangle size={20} />
          Live Signals
        </h3>
        <div className="signals-scroll">
          {signals.map((signal) => (
            <div key={signal.id} className="signal-item">
              <div className="signal-meta">
                {signal.platform} {' '}•{' '} {new Date(signal.posted_at).toLocaleTimeString()}
              </div>
              <div className="signal-text">{signal.text_cleaned}</div>
              <div className="entities">
                {signal.entities?.map((ent, i) => (
                  <span key={i} className="entity-tag">{ent.entity_text}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="main-map">
        <MapContainer center={[22.9734, 78.6569]} zoom={5} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution="&copy; CARTO"
          />
          {signals.map((signal) => (
            <Marker key={signal.id} position={[signal.lat || 23.2599, signal.lng || 77.4126]}>
              <Popup className="custom-popup">
                <strong>{signal.platform} Signal</strong>
                <br />
                {signal.text_cleaned}
              </Popup>
            </Marker>
          ))}
          {hotspots
            .filter((spot) => spot?.center?.coordinates?.length >= 2)
            .map((spot, i) => {
              const intensity = Number(spot.intensity || 1);
              const radius = Math.min(25000, 2000 + intensity * 1200);
              const opacity = Math.min(0.65, 0.2 + intensity * 0.05);
              return (
                <Circle
                  key={i}
                  center={[spot.center.coordinates[1], spot.center.coordinates[0]]}
                  radius={radius}
                  pathOptions={{
                    fillColor: '#ff2d20',
                    color: '#ff6a00',
                    fillOpacity: opacity,
                    weight: 1
                  }}
                >
                  <Popup>
                    <strong>Hotspot Detected</strong>
                    <br />
                    {intensity} related signals in this area.
                  </Popup>
                </Circle>
              );
            })}
        </MapContainer>
      </div>
    </div>
  );
}

export default App;

