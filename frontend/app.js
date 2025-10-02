function getApiBaseUrl() {
    // Use the same origin as the frontend since we have a proxy
    // The frontend server (port 5000) will proxy /api/* requests to backend (port 8000)
    return window.location.origin;
}

const API_BASE_URL = getApiBaseUrl();
console.log('API_BASE_URL:', API_BASE_URL);

let autoRefreshInterval = null;
let isAutoRefresh = false;

const symbolSelect = document.getElementById('symbol');
const timeframeSelect = document.getElementById('timeframe');
const getSignalBtn = document.getElementById('getSignal');
const autoRefreshBtn = document.getElementById('autoRefresh');
const loadingDiv = document.getElementById('loading');
const errorDiv = document.getElementById('error');
const signalCard = document.getElementById('signalCard');

getSignalBtn.addEventListener('click', () => fetchSignal());
autoRefreshBtn.addEventListener('click', toggleAutoRefresh);

symbolSelect.addEventListener('change', () => {
    if (!isAutoRefresh) {
        fetchSignal();
    }
});

async function fetchSignal() {
    const symbol = symbolSelect.value;
    const timeframe = timeframeSelect.value;
    
    loadingDiv.style.display = 'block';
    errorDiv.style.display = 'none';
    signalCard.style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/signal?symbol=${symbol}&timeframe=${timeframe}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        displaySignal(data);
        
        loadingDiv.style.display = 'none';
        signalCard.style.display = 'block';
    } catch (error) {
        loadingDiv.style.display = 'none';
        errorDiv.style.display = 'block';
        errorDiv.textContent = `Error fetching signal: ${error.message}. Make sure the backend API is running on port 8000.`;
    }
}

function displaySignal(data) {
    document.getElementById('signalSymbol').textContent = data.symbol;
    
    const signalBadge = document.getElementById('signalBadge');
    signalBadge.textContent = data.signal;
    signalBadge.className = 'signal-badge ' + data.signal.toLowerCase();
    
    document.getElementById('currentPrice').textContent = '$' + formatNumber(data.current_price);
    document.getElementById('takeProfit').textContent = data.take_profit ? '$' + formatNumber(data.take_profit) : 'N/A';
    document.getElementById('stopLoss').textContent = data.stop_loss ? '$' + formatNumber(data.stop_loss) : 'N/A';
    
    document.getElementById('rsi').textContent = data.rsi ? data.rsi.toFixed(2) : 'N/A';
    document.getElementById('ema12').textContent = data.ema12 ? formatNumber(data.ema12) : 'N/A';
    document.getElementById('ema26').textContent = data.ema26 ? formatNumber(data.ema26) : 'N/A';
    document.getElementById('atr').textContent = data.atr ? formatNumber(data.atr) : 'N/A';
    
    if (data.timeframe_analysis) {
        const ta = data.timeframe_analysis;
        document.getElementById('timeframeAnalysis').innerHTML = `
            <strong>Bullish Timeframes:</strong> ${ta.bullish_timeframes} / ${ta.total_timeframes}<br>
            <strong>Bearish Timeframes:</strong> ${ta.bearish_timeframes} / ${ta.total_timeframes}<br>
            <strong>Timeframes Analyzed:</strong> ${data.timeframes_analyzed ? data.timeframes_analyzed.join(', ') : 'N/A'}
        `;
    }
    
    const confidence = (data.confidence || 0) * 100;
    document.getElementById('confidenceBar').style.width = confidence + '%';
    document.getElementById('confidenceText').textContent = confidence.toFixed(0) + '%';
    
    const reasonsList = document.getElementById('reasonsList');
    reasonsList.innerHTML = '';
    if (data.reasons && data.reasons.length > 0) {
        data.reasons.forEach(reason => {
            const li = document.createElement('li');
            li.textContent = reason;
            reasonsList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'No specific reasons provided';
        reasonsList.appendChild(li);
    }
    
    document.getElementById('timestamp').textContent = `Last updated: ${data.timestamp || new Date().toLocaleString()}`;
}

function formatNumber(num) {
    if (num >= 1000) {
        return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else {
        return num.toFixed(6);
    }
}

function toggleAutoRefresh() {
    isAutoRefresh = !isAutoRefresh;
    
    if (isAutoRefresh) {
        autoRefreshBtn.textContent = 'Auto Refresh: ON';
        autoRefreshBtn.classList.add('active');
        fetchSignal();
        autoRefreshInterval = setInterval(() => {
            fetchSignal();
        }, 30000);
    } else {
        autoRefreshBtn.textContent = 'Auto Refresh: OFF';
        autoRefreshBtn.classList.remove('active');
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }
}

fetchSignal();
