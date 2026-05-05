import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';
import { Activity, AlertTriangle, Shield, Map as MapIcon, RefreshCw, Bell } from 'lucide-react';
import L from 'leaflet';

// Fix for Leaflet default icon
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";
const API_KEY = import.meta.env.VITE_SETU_API_KEY || "";

function App() {
  const [signals, setSignals] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ total_signals: 0, entity_breakdown: [] });
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [signalsRes, statsRes, hotspotsRes, alertsRes] = await Promise.all([
        axios.get(`${API_BASE}/signals`, { headers: API_KEY ? { "x-api-key": API_KEY } : {} }),
        axios.get(`${API_BASE}/stats`, { headers: API_KEY ? { "x-api-key": API_KEY } : {} }),
        axios.get(`${API_BASE}/hotspots`, { headers: API_KEY ? { "x-api-key": API_KEY } : {} }),
        axios.get(`${API_BASE}/alerts`, { headers: API_KEY ? { "x-api-key": API_KEY } : {} })
      ]);
      setSignals(signalsRes.data);
      setStats(statsRes.data);
      setHotspots(hotspotsRes.data);
      setAlerts(alertsRes.data);
      setLoading(false);
    } catch (err) {
      console.error("Fetch error:", err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard-container">
      <header>
        <div className="logo">SETU AAROGYA DRISHTI</div>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <div style={{ color: 'var(--primary)', fontWeight: 'bold' }}>
            <Activity size={16} style={{ marginRight: 8 }} />
            {stats.total_signals} SIGNALS DETECTED
          </div>
          <button onClick={fetchData} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer' }}>
            <RefreshCw size={20} />
          </button>
        </div>
      </header>

      <div className="sidebar">
        {/* Alerts Section */}
        {alerts.length > 0 && (
          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', fontSize: '1rem' }}>
              <Bell size={18} style={{ marginRight: 8 }} />
              Active Alerts
            </h3>
            {alerts.map((alert, i) => (
              <div key={i} className="card" style={{ border: '1px solid var(--danger)', background: 'rgba(255, 75, 43, 0.1)' }}>
                <strong style={{ color: 'var(--danger)' }}>{alert.type}</strong>
                <div style={{ fontSize: '0.8rem' }}>{alert.count} cases of {alert.entity} detected in District {alert.district_id}</div>
              </div>
            ))}
          </div>
        )}

        <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center' }}>
          <AlertTriangle size={20} style={{ marginRight: 10, color: 'var(--primary)' }} />
          Live Signals
        </h3>
        <div style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 300px)' }}>
          {signals.map(signal => (
            <div key={signal.id} className="signal-item">
              <div className="signal-meta">
                {signal.platform} • {new Date(signal.posted_at).toLocaleTimeString()}
              </div>
              <div style={{ fontSize: '0.85rem' }}>{signal.text_cleaned}</div>
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
            attribution='&copy; CARTO'
          />
          {/* Individual Signal Markers */}
          {signals.map(signal => (
            <Marker key={signal.id} position={[signal.lat || 23.2599, signal.lng || 77.4126]}>
              <Popup className="custom-popup">
                <strong>{signal.platform} Signal</strong><br/>
                {signal.text_cleaned}
              </Popup>
            </Marker>
          ))}
          {/* Heatmap/Hotspot Circles */}
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
                    <strong>Hotspot Detected</strong><br/>
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
