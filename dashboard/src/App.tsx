import React, { useState, useEffect } from 'react';
import './App.css';

interface OptionsData {
  timestamp: string;
  spx_level: number;
  spx_change: number;
  confidence: number;
  primary_pin_target: number;
  pin_gamma_concentration: number;
  pin_bias: string;
  momentum_signal: string;
  combined_signal: string;
  trades_processed: number;
  buy_sell_ratio: number;
  avg_trade_size: number;
}

function App() {
  const [data, setData] = useState<OptionsData | null>(null);
  const [status, setStatus] = useState('connecting...');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    console.log('🔌 Attempting to connect to WebSocket...');
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = () => {
      console.log('✅ WebSocket connected');
      setStatus('connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('📊 Received data:', message);
        
        if (message.type === 'dashboard_update') {
          setData(message.data);
          setLastUpdate(new Date());
        }
      } catch (error) {
        console.error('❌ Failed to parse message:', error);
      }
    };
    
    ws.onclose = () => {
      console.log('❌ WebSocket disconnected');
      setStatus('disconnected');
    };
    
    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      setStatus('error');
    };

    return () => {
      console.log('🔌 Closing WebSocket connection');
      ws.close();
    };
  }, []);

  return (
    <div className="App">
      <div className="App-header">
        <h1>🎯 OptionsAgents Dashboard</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div 
            style={{ 
              width: '12px', 
              height: '12px', 
              borderRadius: '50%', 
              backgroundColor: status === 'connected' ? '#10b981' : status === 'connecting...' ? '#f59e0b' : '#ef4444' 
            }}
          />
          <span>Status: {status}</span>
          {lastUpdate && <span style={{ marginLeft: '20px', fontSize: '14px', opacity: 0.7 }}>
            Last update: {lastUpdate.toLocaleTimeString()}
          </span>}
        </div>
      </div>
      
      <div className="dashboard">
        {status === 'error' && (
          <div className="status" style={{ backgroundColor: '#7f1d1d', color: '#fca5a5' }}>
            ❌ Connection Error: Make sure the Python backend is running on port 8000
            <br />
            <code>python -m src.api.dashboard</code>
          </div>
        )}
        
        {status === 'connecting...' && (
          <div className="status" style={{ backgroundColor: '#92400e', color: '#fbbf24' }}>
            🔌 Connecting to backend...
          </div>
        )}
        
        {data && (
          <div>
            <h2>📈 Live Market Data</h2>
            
            <div className="grid">
              <div className="data-card">
                <h3>SPX Level</h3>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: data.spx_change >= 0 ? '#10b981' : '#ef4444' }}>
                  {data.spx_level.toFixed(2)}
                </div>
                <div style={{ color: data.spx_change >= 0 ? '#10b981' : '#ef4444' }}>
                  {data.spx_change >= 0 ? '+' : ''}{data.spx_change.toFixed(2)}
                </div>
              </div>
              
              <div className="data-card">
                <h3>🎯 Pin Target</h3>
                <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                  ${data.primary_pin_target}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.8 }}>
                  {data.pin_gamma_concentration}γ concentration
                </div>
              </div>
              
              <div className="data-card">
                <h3>📊 Signals</h3>
                <div><strong>Pin:</strong> {data.pin_bias}</div>
                <div><strong>Momentum:</strong> {data.momentum_signal}</div>
                <div><strong>Combined:</strong> <span style={{ fontWeight: 'bold' }}>{data.combined_signal}</span></div>
              </div>
              
              <div className="data-card">
                <h3>🔍 Analysis</h3>
                <div><strong>Confidence:</strong> {data.confidence}%</div>
                <div><strong>Trades:</strong> {data.trades_processed.toLocaleString()}</div>
                <div><strong>B/S Ratio:</strong> {data.buy_sell_ratio}</div>
              </div>
            </div>
            
            <div className="data-card" style={{ marginTop: '20px' }}>
              <h3>📝 Raw Data</h3>
              <pre className="live-data" style={{ fontSize: '12px', overflow: 'auto' }}>
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
