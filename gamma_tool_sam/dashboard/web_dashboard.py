"""
Web Dashboard for Gamma Tool Sam
Provides real-time visualization of gamma analysis
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Global reference to gamma engine (will be set by runner)
gamma_engine = None

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    """API endpoint for real-time data"""
    if not gamma_engine:
        return jsonify({'status': 'not_initialized'})
        
    try:
        data = gamma_engine.get_dashboard_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary')
def get_summary():
    """Agent API endpoint - full summary"""
    if not gamma_engine:
        return jsonify({'error': 'System not initialized'}), 503
        
    return jsonify(gamma_engine.get_pin_summary())

@app.route('/api/strongest-pin')
def get_strongest_pin():
    """Agent API endpoint - strongest pin only"""
    if not gamma_engine:
        return jsonify({'error': 'System not initialized'}), 503
        
    pin = gamma_engine.get_strongest_pin()
    if pin:
        return jsonify(pin)
    else:
        return jsonify({'message': 'No pin data available'}), 404

@app.route('/api/risk')
def get_risk():
    """Agent API endpoint - risk assessment"""
    if not gamma_engine:
        return jsonify({'error': 'System not initialized'}), 503
        
    return jsonify(gamma_engine.calculate_risk_level())

@app.route('/api/confidence')
def get_confidence():
    """Agent API endpoint - detailed confidence analysis"""
    if not gamma_engine:
        return jsonify({'error': 'System not initialized'}), 503
        
    return jsonify(gamma_engine.get_confidence_analysis())

@app.route('/api/spikes')
def get_spikes():
    """Agent API endpoint - recent spikes"""
    if not gamma_engine:
        return jsonify({'error': 'System not initialized'}), 503
        
    minutes = request.args.get('minutes', 5, type=int)
    return jsonify({'spikes': gamma_engine.get_recent_spikes(minutes)})

def create_dashboard_html():
    """Create the HTML template"""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Gamma Tool Sam - Live Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Courier New', monospace;
            background-color: #0a0a0a;
            color: #00ff00;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        
        .header h1 {
            margin: 0;
            font-size: 24px;
            text-shadow: 0 0 10px #00ff00;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .panel {
            background-color: #1a1a1a;
            border: 1px solid #00ff00;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.1);
        }
        
        .panel h2 {
            margin: 0 0 10px 0;
            font-size: 18px;
            color: #00ff00;
            text-transform: uppercase;
        }
        
        .force-indicator {
            font-size: 36px;
            font-weight: bold;
            text-align: center;
            margin: 10px 0;
        }
        
        .upward { color: #00ff00; }
        .downward { color: #ff0066; }
        
        .pin-bar {
            background-color: #333;
            height: 20px;
            margin: 5px 0;
            position: relative;
            border-radius: 3px;
            overflow: hidden;
        }
        
        .pin-fill {
            height: 100%;
            background-color: #00ff00;
            transition: width 0.3s ease;
        }
        
        .pin-fill.downward {
            background-color: #ff0066;  /* Red for downward pins */
        }
        
        .pin-label {
            position: absolute;
            left: 5px;
            top: 2px;
            font-size: 12px;
            color: #fff;  /* White text for better contrast */
            font-weight: bold;
            text-shadow: 0 0 3px rgba(0, 0, 0, 0.8);  /* Dark outline for readability */
        }
        
        .alert {
            background-color: #330000;
            border: 1px solid #ff0066;
            border-radius: 3px;
            padding: 8px;
            margin: 5px 0;
            font-size: 14px;
        }
        
        .alert.critical {
            animation: blink 1s infinite;
        }
        
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.5; }
        }
        
        .signal {
            text-align: center;
            font-size: 20px;
            padding: 10px;
            margin: 10px 0;
            border: 2px solid;
            border-radius: 5px;
        }
        
        .signal.long { 
            border-color: #00ff00;
            background-color: rgba(0, 255, 0, 0.1);
        }
        
        .signal.short { 
            border-color: #ff0066;
            background-color: rgba(255, 0, 102, 0.1);
        }
        
        .signal.wait { 
            border-color: #ffff00;
            background-color: rgba(255, 255, 0, 0.1);
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin-top: 10px;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
        }
        
        .stat-label {
            font-size: 12px;
            color: #888;
        }
        
        #timestamp {
            text-align: center;
            color: #888;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 GAMMA TOOL SAM - LIVE DASHBOARD</h1>
            <div id="spx-price">SPX: Loading...</div>
        </div>
        
        <div class="grid">
            <div class="panel">
                <h2>Directional Force</h2>
                <div id="net-force" class="force-indicator">--</div>
                <div id="confidence-bar" class="pin-bar">
                    <div class="pin-fill" style="width: 0%"></div>
                    <div class="pin-label">Confidence: 0%</div>
                </div>
                <div id="confidence-explanation" style="font-size: 12px; margin-top: 5px; color: #888;"></div>
            </div>
            
            <div class="panel">
                <h2>Trading Signal</h2>
                <div id="trading-signal" class="signal wait">
                    WAITING FOR DATA...
                </div>
            </div>
        </div>
        
        <div class="grid">
            <div class="panel">
                <h2>⬆️ Upward Pins</h2>
                <div id="upward-pins"></div>
            </div>
            
            <div class="panel">
                <h2>⬇️ Downward Pins</h2>
                <div id="downward-pins"></div>
            </div>
        </div>
        
        <div class="panel">
            <h2>⚡ Active Alerts</h2>
            <div id="alerts"></div>
        </div>
        
        <div class="panel">
            <h2>📊 Statistics</h2>
            <div class="stats">
                <div class="stat">
                    <div id="trades-count" class="stat-value">0</div>
                    <div class="stat-label">Trades Processed</div>
                </div>
                <div class="stat">
                    <div id="strikes-active" class="stat-value">0</div>
                    <div class="stat-label">Active Strikes</div>
                </div>
                <div class="stat">
                    <div id="upward-force" class="stat-value">0</div>
                    <div class="stat-label">Upward Force</div>
                </div>
                <div class="stat">
                    <div id="downward-force" class="stat-value">0</div>
                    <div class="stat-label">Downward Force</div>
                </div>
            </div>
        </div>
        
        <div id="timestamp">Last Update: --</div>
    </div>
    
    <script>
        function formatNumber(num) {
            return new Intl.NumberFormat('en-US').format(Math.round(num));
        }
        
        function updateDashboard() {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'waiting_for_data') {
                        return;
                    }
                    
                    // Update SPX price
                    document.getElementById('spx-price').textContent = 
                        `SPX: $${formatNumber(data.spx_price)}`;
                    
                    // Update directional force
                    const forceElement = document.getElementById('net-force');
                    const force = data.net_force;
                    forceElement.textContent = `${force > 0 ? '+' : ''}${formatNumber(force)} ${force > 0 ? '↑' : '↓'}`;
                    forceElement.className = `force-indicator ${force > 0 ? 'upward' : 'downward'}`;
                    
                    // Update confidence
                    const confidence = Math.round(data.confidence * 100);
                    document.querySelector('#confidence-bar .pin-fill').style.width = `${confidence}%`;
                    document.querySelector('#confidence-bar .pin-label').textContent = `Confidence: ${confidence}%`;
                    
                    // Update confidence explanation if available
                    const explanationEl = document.getElementById('confidence-explanation');
                    if (data.confidence_details && data.confidence_details.explanation) {
                        explanationEl.textContent = data.confidence_details.explanation.slice(0, 2).join(' • ');
                    }
                    
                    // Update trading signal
                    const signal = data.signal;
                    const signalElement = document.getElementById('trading-signal');
                    if (signal.action === 'LONG') {
                        signalElement.className = 'signal long';
                        signalElement.innerHTML = `LONG → ${signal.target}<br>Stop: ${signal.stop}<br><small>Buy SPX/Calls</small>`;
                    } else if (signal.action === 'SHORT') {
                        signalElement.className = 'signal short';
                        signalElement.innerHTML = `SHORT → ${signal.target}<br>Stop: ${signal.stop}<br><small>Buy Puts/Short SPX</small>`;
                    } else {
                        signalElement.className = 'signal wait';
                        signalElement.innerHTML = `WAIT<br>${signal.reason}`;
                    }
                    
                    // Update pins
                    updatePins('upward-pins', data.pins.upward);
                    updatePins('downward-pins', data.pins.downward);
                    
                    // Update alerts
                    updateAlerts(data.alerts);
                    
                    // Update stats
                    document.getElementById('trades-count').textContent = 
                        formatNumber(data.stats.trades_processed);
                    document.getElementById('strikes-active').textContent = 
                        data.stats.strikes_active;
                    document.getElementById('upward-force').textContent = 
                        formatNumber(Math.abs(data.upward_force || 0));
                    document.getElementById('downward-force').textContent = 
                        formatNumber(Math.abs(data.downward_force || 0));
                    
                    // Update timestamp
                    document.getElementById('timestamp').textContent = 
                        `Last Update: ${new Date(data.timestamp).toLocaleTimeString()}`;
                })
                .catch(error => console.error('Error:', error));
        }
        
        function updatePins(elementId, pins) {
            const container = document.getElementById(elementId);
            container.innerHTML = '';
            
            const isDownward = elementId === 'downward-pins';
            
            pins.forEach(pin => {
                const maxForce = 1000000; // 1M for scaling
                const width = Math.min((pin.force / maxForce) * 100, 100);
                
                const pinHtml = `
                    <div class="pin-bar">
                        <div class="pin-fill ${isDownward ? 'downward' : ''}" style="width: ${width}%"></div>
                        <div class="pin-label">${pin.strike}: ${formatNumber(pin.force)}</div>
                    </div>
                `;
                container.innerHTML += pinHtml;
            });
        }
        
        function updateAlerts(alerts) {
            const container = document.getElementById('alerts');
            container.innerHTML = '';
            
            alerts.slice(0, 5).forEach(alert => {
                const severity = alert.severity.toLowerCase();
                let directionSymbol = '';
                let directionClass = '';
                
                // Add direction symbols for pins and spikes
                if (alert.direction) {
                    if (alert.direction === 'UPWARD') {
                        directionSymbol = ' ↑';
                        directionClass = ' upward';
                    } else if (alert.direction === 'DOWNWARD') {
                        directionSymbol = ' ↓';
                        directionClass = ' downward';
                    } else {
                        directionSymbol = ' ↔';
                        directionClass = '';
                    }
                }
                
                const alertHtml = `
                    <div class="alert ${severity}${directionClass}">
                        ${alert.type}: ${alert.details.volume || ''}x 
                        ${alert.strike || ''} 
                        @ ${new Date(alert.timestamp).toLocaleTimeString()}${directionSymbol}
                    </div>
                `;
                container.innerHTML += alertHtml;
            });
        }
        
        // Update every 2 seconds
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>"""
    
    # Create templates directory
    os.makedirs('gamma_tool_sam/dashboard/templates', exist_ok=True)
    
    # Write HTML file
    with open('gamma_tool_sam/dashboard/templates/dashboard.html', 'w') as f:
        f.write(html_content)

# Create the HTML template when module loads
create_dashboard_html()

def run_dashboard(engine, host='0.0.0.0', port=8080):
    """Run the web dashboard"""
    global gamma_engine
    gamma_engine = engine
    
    print(f"\n🌐 Web Dashboard running at http://localhost:{port}")
    app.run(host=host, port=port, debug=False)