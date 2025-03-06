// Wait for DOM to be loaded
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM loaded - initializing dashboard");
    
    // Grab UI elements
    const connectionStatus = document.getElementById('connection-status');
    const refreshButton = document.getElementById('refresh-btn');
    const tradingToggleBtn = document.getElementById('trading-toggle-btn');
    const tradeModeSelect = document.getElementById('trade-mode-select');
    const percentageControls = document.getElementById('percentage-controls');
    const fixedAmountControls = document.getElementById('fixed-amount-controls');
    const saveTradeSettingsBtn = document.getElementById('save-trade-settings');
    const tradePercentageInput = document.getElementById('trade-percentage');
    const fixedAmountInput = document.getElementById('fixed-amount');
    const themeToggle = document.getElementById('theme-toggle');
    const themeOptions = document.getElementById('theme-options');
    const docsBtn = document.getElementById('docs-btn');
    const helpModal = document.getElementById('help-modal');
    const closeModalBtn = document.querySelector('.close-modal');
    const activityLog = document.getElementById('activity-log');
    
    console.log("Activity log element found:", !!activityLog);
    
    // Initialize socket.io connection
    const socket = io();
    
    // MAKE ACTIVITY HISTORY GLOBAL so it's accessible everywhere
    window.activityHistory = [];
    
    // Socket events
    socket.on('connect', function() {
        connectionStatus.innerHTML = '<i class="fas fa-circle-check" style="color: green;"></i> Connected';
    });
    
    socket.on('disconnect', function() {
        connectionStatus.innerHTML = '<i class="fas fa-circle-xmark" style="color: red;"></i> Disconnected';
    });
    
    socket.on('data_update', function(data) {
        updateDashboard(data);
    });
    
    // Event listeners for UI controls
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
            
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    updateDashboard(data);
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
                })
                .catch(error => {
                    console.error('Error refreshing data:', error);
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
                });
        });
    }
    
    if (tradingToggleBtn) {
        tradingToggleBtn.addEventListener('click', function() {
            const currentState = this.classList.contains('btn-danger');
            const newState = !currentState;
            
            // Disable button during transition
            this.disabled = true;
            
            // API call to toggle trading state
            fetch('/api/toggle_trading', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled: newState })
            })
            .then(response => response.json())
            .then(data => {
                // Update button based on response
                updateAllTradingUIComponents(data.trading_enabled);
                this.disabled = false;
            })
            .catch(error => {
                console.error('Error toggling trading:', error);
                this.disabled = false;
            });
        });
    }
    
    // Handle theme toggling
    if (themeToggle) {
        themeToggle.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent document click from immediately closing menu
            themeOptions.classList.toggle('show');
        });
        
        // Close the theme options when clicking outside
        document.addEventListener('click', function() {
            themeOptions.classList.remove('show');
        });
        
        // Theme selection
        document.querySelectorAll('.theme-option').forEach(option => {
            option.addEventListener('click', function(e) {
                e.stopPropagation(); // Prevent document click from handling this click
                const theme = this.getAttribute('data-theme');
                setTheme(theme);
                themeOptions.classList.remove('show');
            });
        });
    }
    
    // Initialize theme from localStorage or default to auto
    const savedTheme = localStorage.getItem('preferred-theme') || 'auto';
    setTheme(savedTheme);
    
    // Auto theme should listen for system preferences
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function() {
        if (localStorage.getItem('preferred-theme') === 'auto') {
            setTheme('auto');
        }
    });
    
    // Handle modal
    if (docsBtn && helpModal) {
        docsBtn.addEventListener('click', function() {
            helpModal.style.display = 'flex';
        });
        
        closeModalBtn.addEventListener('click', function() {
            helpModal.style.display = 'none';
        });
        
        // Close when clicking outside the modal content
        helpModal.addEventListener('click', function(e) {
            if (e.target === helpModal) {
                helpModal.style.display = 'none';
            }
        });
    }
    
    // Initialize trade settings
    initTradeSettings();
});

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    // Return full date and time format: YYYY-MM-DD HH:MM:SS
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function getTimeAgo(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) {
        return 'just now';
    }
    
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
        return `${minutes}m ago`;
    }
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return `${hours}h ago`;
    }
    
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// Function to update or create price chart
function updatePriceChart(symbolKey, data) {
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded yet, delaying chart update');
        setTimeout(() => updatePriceChart(symbolKey, data), 500);
        return;
    }

    const chartCanvas = document.getElementById(`price-chart-${symbolKey}`);
    
    if (!chartCanvas) {
        console.error(`Chart canvas not found for ${symbolKey}`);
        return;
    }
    
    console.log(`Updating price chart for ${symbolKey}`);
    
    // Ensure canvas dimensions are correctly set
    const containerWidth = chartCanvas.parentElement.clientWidth;
    chartCanvas.width = containerWidth;
    chartCanvas.height = 120;
    
    // Skip if no price history data is available
    if (!data.price_history || !data.price_history.prices || data.price_history.prices.length === 0) {
        console.log(`No price history data for ${symbolKey}`);
        
        // Safely destroy existing chart if present
        if (chartCanvas._chart) {
            try {
                chartCanvas._chart.destroy();
            } catch (e) {
                console.error(`Error destroying chart for ${symbolKey}:`, e);
            }
            chartCanvas._chart = null;
        }
        
        // Draw "No data available" text on canvas
        try {
            const ctx = chartCanvas.getContext('2d');
            if (ctx) {
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                ctx.font = '12px Inter';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#64748b';
                ctx.fillText('No price history available', chartCanvas.width / 2, chartCanvas.height / 2);
            }
        } catch (e) {
            console.error(`Error drawing text on canvas for ${symbolKey}:`, e);
        }
        return;
    }
    
    try {
        // Format data for Chart.js with safe access to properties
        const prices = data.price_history.prices || [];
        const timestamps = (data.price_history.timestamps || []).map(ts => {
            try {
                const date = new Date(ts);
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                return '';
            }
        });
        
        // Get market statuses if available with fallback
        const marketStatuses = data.price_history.market_statuses || Array(prices.length).fill('open');
        
        // Prepare point styles and sizes based on market status
        const pointStyles = marketStatuses.map(status => {
            switch(status) {
                case 'pre_market': return 'triangle';
                case 'after_hours': return 'rectRot'; 
                case 'closed': return 'crossRot';
                case 'open':
                default: return 'circle';
            }
        });
        
        const pointSizes = marketStatuses.map(status => {
            switch(status) {
                case 'pre_market': 
                case 'after_hours': return 3;
                case 'closed': return 4;
                case 'open':
                default: return 2;
            }
        });
        
        // Determine chart color based on trend
        let borderColor = '#3b82f6'; // Default blue
        if (prices.length > 1) {
            const firstPrice = prices[0];
            const lastPrice = prices[prices.length - 1];
            if (lastPrice > firstPrice) {
                borderColor = '#10b981'; // Green for uptrend
            } else if (lastPrice < firstPrice) {
                borderColor = '#ef4444'; // Red for downtrend
            }
        }
        
        // Update or create chart
        if (chartCanvas._chart) {
            try {
                // Update existing chart
                chartCanvas._chart.data.labels = timestamps;
                chartCanvas._chart.data.datasets[0].data = prices;
                chartCanvas._chart.data.datasets[0].borderColor = borderColor;
                chartCanvas._chart.data.datasets[0].pointRadius = pointSizes;
                chartCanvas._chart.data.datasets[0].pointStyle = pointStyles;
                chartCanvas._chart.update('none'); // Use 'none' mode for better performance
            } catch (e) {
                console.error(`Error updating chart for ${symbolKey}:`, e);
                // Destroy and recreate on error
                try {
                    chartCanvas._chart.destroy();
                } catch (e) {
                    console.error(`Error destroying chart after update error:`, e);
                }
                chartCanvas._chart = null;
            }
        }
        
        if (!chartCanvas._chart) {
            try {
                console.log(`Creating new chart for ${symbolKey}`);
                // Create new chart
                chartCanvas._chart = new Chart(chartCanvas, {
                    type: 'line',
                    data: {
                        labels: timestamps,
                        datasets: [{
                            label: 'Price',
                            data: prices,
                            borderColor: borderColor,
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: pointSizes,
                            pointStyle: pointStyles,
                            pointHoverRadius: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            duration: 400
                        },
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                enabled: true,
                                mode: 'index',
                                intersect: false,
                                callbacks: {
                                    label: function(context) {
                                        return `$${parseFloat(context.raw).toFixed(2)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: false,
                                ticks: {
                                    display: true,
                                    color: '#64748b',
                                    font: {
                                        size: 10
                                    },
                                    callback: function(value) {
                                        return '$' + parseFloat(value).toFixed(0);
                                    }
                                },
                                grid: {
                                    display: true,
                                    color: 'rgba(203, 213, 225, 0.2)'
                                }
                            },
                            x: {
                                ticks: {
                                    display: true,
                                    color: '#64748b',
                                    font: {
                                        size: 8
                                    },
                                    maxRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 5
                                },
                                grid: {
                                    display: false
                                }
                            }
                        }
                    }
                });
            } catch (e) {
                console.error(`Error creating chart for ${symbolKey}:`, e);
            }
        }
    } catch (e) {
        console.error(`Error processing chart data for ${symbolKey}:`, e);
    }
}

function updateSymbolCard(symbol, data) {
    const symbolKey = symbol.replace('/', '-');
    const card = document.getElementById(`card-${symbolKey}`);
    
    if (!card) return;
    
    const rsiElement = document.getElementById(`rsi-${symbolKey}`);
    const decisionElement = document.getElementById(`decision-${symbolKey}`);
    const statusElement = document.getElementById(`status-${symbolKey}`);
    const updatedElement = document.getElementById(`updated-${symbolKey}`);
    const tradeInfoElement = document.getElementById(`trade-info-${symbolKey}`);
    
    // Update RSI value
    if (data.rsi && data.rsi.value !== undefined) {
        rsiElement.textContent = data.rsi.value.toFixed(2);
    } else {
        rsiElement.textContent = '--';
    }
    
    // Update decision
    if (data.signal && data.signal.decision) {
        decisionElement.textContent = data.signal.decision.toUpperCase();
        decisionElement.className = 'metric-value decision ' + data.signal.decision.toLowerCase();
    } else {
        decisionElement.textContent = '--';
        decisionElement.className = 'metric-value decision';
    }
    
    // Update trade status
    if (data.result && data.result.status) {
        statusElement.textContent = data.result.status.charAt(0).toUpperCase() + data.result.status.slice(1);
    } else {
        statusElement.textContent = '--';
    }
    
    // Update timestamp
    if (data.timestamp) {
        updatedElement.textContent = `Updated ${getTimeAgo(data.timestamp)}`;
    } else {
        updatedElement.textContent = 'No data';
    }
    
    // Update price chart
    updatePriceChart(symbolKey, data);
    
    // Get info about order status
    const isExecutedTrade = data.result && data.result.status === 'executed';
    const isSkippedTrade = data.result && data.result.status === 'skipped';
    const isFailedTrade = data.result && data.result.status === 'failed';
    
    // Check if trading is enabled from the system data
    const tradingEnabled = window.latestSystemData && window.latestSystemData.trading_enabled;
    
    // Check if this is a disabled message from the backend - SIMPLE SERVICE LEVEL APPROACH
    const isDisabledMessage = data.result && 
                             data.result.status === 'skipped' && 
                             data.result.error === 'Trading is currently disabled';
                             
    // FIXED LOGIC FLOW - put most specific conditions first
    // 1. Trading disabled has highest priority
    // DIRECT APPROACH: If we see this is a skipped message due to disabled trading
    if (data.result && data.result.status === 'skipped' && data.result.error === 'Trading is currently disabled') {
        console.log(`DEFINITELY FOUND disabled message for ${symbol}: ${data.result.error}`);
        console.log("ENTIRE RESULT OBJECT:", JSON.stringify(data.result));
        tradeInfoElement.innerHTML = `
            <div class="trade-details trade-skipped">
                <strong>Trade skipped:</strong> Trading is currently disabled (${new Date().toLocaleTimeString()})
            </div>
        `;
        return; // EXIT NOW - don't let any other logic run
    }
    // 2. Show executed trades next
    else if (isExecutedTrade) {
        const tradeTime = formatTimestamp(data.result.timestamp);
        const action = data.result.decision.toUpperCase();
        const quantity = data.result.quantity ? data.result.quantity.toFixed(4) : '?';
        const price = data.result.price ? `$${data.result.price.toFixed(2)}` : '?';
        
        // Change the class for the entire div if it's a SELL transaction
        const tradeClass = action === 'SELL' ? 'trade-details trade-executed sell-transaction' : 'trade-details trade-executed';
        
        tradeInfoElement.innerHTML = `
            <div class="${tradeClass}">
                <strong>${action}</strong> ${quantity} units at ${price} (${tradeTime})
                <div>Order ID: ${data.result.order_id || 'Pending'}</div>
            </div>
        `;
    } 
    // 3. Failed trades
    else if (isFailedTrade) {
        tradeInfoElement.innerHTML = `
            <div class="trade-details trade-failed">
                <strong>Trade failed:</strong> ${data.result.error || 'Unknown error'}
            </div>
        `;
    } 
    // 4. Other skipped trades with error information
    else if (isSkippedTrade && data.result.error) {
        tradeInfoElement.innerHTML = `
            <div class="trade-details trade-skipped">
                <strong>Trade skipped:</strong> ${data.result.error}
            </div>
        `;
    } 
    // 5. Default - no trades
    else {
        tradeInfoElement.innerHTML = `<div class="trade-details">No recent trades</div>`;
    }
    
    // Record activity - Show all buy/sell signals regardless of trading status
    if (data.signal && data.signal.decision && data.timestamp) {
        // Never show HOLD decisions in recent activity
        if (data.signal.decision.toLowerCase() === 'hold') {
            return; // Skip adding HOLD signals to activity
        }
        
        // Always show buy/sell signals in recent activity, regardless of trading status
        const action = data.signal.decision.toLowerCase();
        const timestamp = data.timestamp;
        
        // Add to activity if not already in history
        const historyItem = {
            symbol,
            action,
            timestamp,
            rsi: data.rsi ? data.rsi.value : null,
            status: data.result ? data.result.status : null
        };
        
        console.log(`Adding to activity history: ${symbol} ${action} (${historyItem.status || 'no status'})`);
        
        // Check if this event is already in the history
        const isDuplicate = window.activityHistory.some(item => 
            item.symbol === symbol && 
            item.action === action && 
            item.timestamp === timestamp
        );
        
        if (!isDuplicate) {
            window.activityHistory.unshift(historyItem);
            // Keep history limited to 50 items
            if (window.activityHistory.length > 50) {
                window.activityHistory.pop();
            }
            console.log(`Activity history now has ${window.activityHistory.length} items`);
            updateActivityLog();
        }
    }
}

function updateActivityLog() {
    const activityLog = document.getElementById('activity-log');
    
    if (!activityLog) {
        console.error("Activity log element not found!");
        return;
    }
    
    if (!window.activityHistory || window.activityHistory.length === 0) {
        console.log("Activity history is empty, showing empty log message");
        activityLog.innerHTML = '<div class="empty-log">No recent activity</div>';
        return;
    }
    
    console.log(`Updating activity log with ${window.activityHistory.length} items`);
    
    let html = '';
    window.activityHistory.forEach(item => {
        const time = formatTimestamp(item.timestamp);
        
        let icon;
        if (item.action === 'buy') {
            icon = '<i class="fas fa-arrow-up"></i>';
        } else if (item.action === 'sell') {
            icon = '<i class="fas fa-arrow-down"></i>';
        } else {
            icon = '<i class="fas fa-minus"></i>';
        }
        
        // Add RSI value if available
        const rsiText = item.rsi !== null ? `RSI: ${item.rsi.toFixed(2)}` : '';
        
        // Add status badge for all trades, not just executed ones
        let statusBadge = '';
        if (item.status === 'executed') {
            statusBadge = '<span style="font-size: 0.75em; padding: 2px 6px; border-radius: 3px; margin-left: 5px; background-color: #10b981; color: white;">Executed</span>';
        } else if (item.status === 'skipped') {
            statusBadge = '<span style="font-size: 0.75em; padding: 2px 6px; border-radius: 3px; margin-left: 5px; background-color: #f59e0b; color: white;">Skipped</span>';
        } else if (item.status === 'failed') {
            statusBadge = '<span style="font-size: 0.75em; padding: 2px 6px; border-radius: 3px; margin-left: 5px; background-color: #ef4444; color: white;">Failed</span>';
        }
        
        html += `
            <div class="activity-item ${item.action}">
                ${icon}
                <div class="activity-details">
                    <strong>${item.symbol}</strong> 
                    <span class="activity-action">${item.action.toUpperCase()}</span>
                    ${rsiText ? `<span class="activity-rsi">(${rsiText})</span>` : ''}
                    ${statusBadge}
                </div>
                <span class="activity-timestamp" title="${time}">${time}</span>
            </div>
        `;
    });
    
    activityLog.innerHTML = html;
}

function updateDashboard(data) {
    // Store the last received data for force-redrawing without server refresh
    window.lastReceivedData = data;
    
    // Get trading status but DON'T clear executed trades
    // This allows us to show trade history in Recent Activity
    const tradingEnabled = data._system && data._system.trading_enabled;
    
    // Store system data for other functions to access
    if (data._system) {
        window.latestSystemData = data._system;
    }
    
    // Update Ollama status if present
    if (data._system && data._system.ollama_status) {
        updateOllamaStatus(data._system.ollama_status);
    }
    
    // Update trading enabled status in UI if provided
    if (data._system && data._system.trading_enabled !== undefined) {
        const tradingEnabled = data._system.trading_enabled;
        console.log("Trading enabled status from server:", tradingEnabled);
        
        // Use centralized function to update all trading UI components
        updateAllTradingUIComponents(tradingEnabled);
    }
    
    // DIAGNOSTIC: Check what data we're getting
    console.log("RECEIVED DATA UPDATE:", Object.keys(data));
    
    // LOOK DIRECTLY at the symbol data to see what's there
    if (data["BTC/USDT"]) {
        console.log("💰 BTC/USDT full data:", JSON.stringify(data["BTC/USDT"]));
    }
    if (data["ETH/USDT"]) {
        console.log("💰 ETH/USDT full data:", JSON.stringify(data["ETH/USDT"]));
    }
    
    // CRUCIAL: If we have trade results directly available, log them
    if (data._trade_results) {
        console.log("Direct trade results:", Object.keys(data._trade_results));
        // Check if any have the "Trading is disabled" message
        Object.entries(data._trade_results).forEach(([key, result]) => {
            if (result.error === "Trading is currently disabled") {
                console.log(`🔍 Found disabled message in _trade_results: ${key}`);
            }
        });
    }
    
    // Update each symbol card - with extra diagnostics
    Object.keys(data).forEach(symbol => {
        if (symbol !== '_system' && symbol !== '_debug' && symbol !== '_trade_results') {
            // CRUCIAL DEBUG CHECK: Check if this symbol has a disabled message
            if (data[symbol] && data[symbol].result && 
                data[symbol].result.status === 'skipped' && 
                data[symbol].result.error === 'Trading is currently disabled') {
                console.log(`🎯 FOUND disabled message for ${symbol} just before updating card!`);
                console.log(JSON.stringify(data[symbol].result));
            }
            
            // Debug price history data
            if (data[symbol] && data[symbol].price_history) {
                console.log(`Price history for ${symbol}: ${data[symbol].price_history.prices?.length || 0} points`);
            } else {
                console.log(`No price history for ${symbol}`);
            }
            
            // Update the card with whatever we have
            updateSymbolCard(symbol, data[symbol]);
            
            // Charts are already rendered during updateSymbolCard
        }
    });
}

function updateOllamaStatus(ollamaStatus) {
    const container = document.getElementById('ollama-status-container');
    const statusText = document.getElementById('ollama-status-text');
    const statusIcon = document.querySelector('#ollama-status i');
    
    if (!ollamaStatus) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'flex';
    container.className = 'status-indicator ' + ollamaStatus.status;
    
    // Set appropriate icon based on status
    if (ollamaStatus.status === 'downloading' || ollamaStatus.status === 'initializing') {
        statusIcon.className = 'fas fa-spinner fa-spin';
    } else if (ollamaStatus.status === 'ready') {
        statusIcon.className = 'fas fa-check-circle';
    } else if (ollamaStatus.status === 'error') {
        statusIcon.className = 'fas fa-exclamation-circle';
    } else {
        statusIcon.className = 'fas fa-robot';
    }
    
    // Set the status message
    statusText.textContent = ollamaStatus.message || 'Unknown';
}

// Initial data fetch
fetch('/api/data')
    .then(response => response.json())
    .then(data => {
        updateDashboard(data);
        
        // Explicitly populate activity history from all signals in data
        console.log("Populating activity history from initial data load");
        Object.keys(data).forEach(symbol => {
            if (symbol.startsWith('_')) return; // Skip system keys
            
            const symbolData = data[symbol];
            if (symbolData && symbolData.signal && symbolData.signal.decision) {
                // Only add buy/sell decisions (skip hold)
                const decision = symbolData.signal.decision.toLowerCase();
                if (decision !== 'hold') {
                    const timestamp = symbolData.timestamp || new Date().toISOString();
                    const historyItem = {
                        symbol,
                        action: decision,
                        timestamp,
                        rsi: symbolData.rsi ? symbolData.rsi.value : null,
                        status: symbolData.result ? symbolData.result.status : null
                    };
                    
                    // Add to history if not a duplicate
                    const isDuplicate = window.activityHistory.some(item => 
                        item.symbol === symbol && 
                        item.action === decision && 
                        item.timestamp === timestamp
                    );
                    
                    if (!isDuplicate) {
                        window.activityHistory.unshift(historyItem);
                        console.log(`Added ${decision} signal for ${symbol} to activity history`);
                    }
                }
            }
        });
        
        // Update activity log with initial history
        if (window.activityHistory.length > 0) {
            console.log(`Updating activity log with ${window.activityHistory.length} initial items`);
            updateActivityLog();
        } else {
            console.log("No items in activity history after initial load");
            
            // DEBUG: Force add a test item to see if the activity log updates
            window.activityHistory.unshift({
                symbol: "TEST/SIGNAL",
                action: "buy",
                timestamp: new Date().toISOString(),
                rsi: 30.5,
                status: "test"
            });
            console.log("Added test item to activity history");
            updateActivityLog();
        }
    })
    .catch(error => {
        console.error('Error fetching initial data:', error);
    });

// Theme management functions
function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setTheme(theme) {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    
    // Remove all existing theme options active class
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.remove('active');
    });
    
    // Add active class to selected option
    const selectedOption = document.querySelector(`.theme-option[data-theme="${theme}"]`);
    if (selectedOption) {
        selectedOption.classList.add('active');
    }
    
    if (theme === 'auto') {
        // Set theme based on system preference
        themeText.textContent = 'Auto';
        themeIcon.className = 'fas fa-adjust';
        
        const systemTheme = getSystemTheme();
        document.documentElement.setAttribute('data-theme', systemTheme);
        localStorage.setItem('preferred-theme', 'auto');
    } else {
        // Set specific theme
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('preferred-theme', theme);
        
        if (theme === 'dark') {
            themeText.textContent = 'Dark';
            themeIcon.className = 'fas fa-moon';
        } else {
            themeText.textContent = 'Light';
            themeIcon.className = 'fas fa-sun';
        }
    }
}

// Handle trade mode settings
function initTradeSettings() {
    if (tradeModeSelect) {
        tradeModeSelect.addEventListener('change', function() {
            const mode = this.value;
            
            if (mode === 'percentage') {
                percentageControls.style.display = 'flex';
                fixedAmountControls.style.display = 'none';
            } else if (mode === 'fixed') {
                percentageControls.style.display = 'none';
                fixedAmountControls.style.display = 'flex';
            }
        });
    }
    
    if (saveTradeSettingsBtn) {
        saveTradeSettingsBtn.addEventListener('click', function() {
            const mode = tradeModeSelect.value;
            const settings = {
                mode: mode
            };
            
            if (mode === 'percentage') {
                settings.percentage = parseFloat(tradePercentageInput.value);
            } else if (mode === 'fixed') {
                settings.fixed_amount = parseFloat(fixedAmountInput.value);
            }
            
            // Validate input
            let valid = true;
            if (mode === 'percentage' && (isNaN(settings.percentage) || settings.percentage <= 0 || settings.percentage > 100)) {
                alert('Percentage must be between 0.1 and 100');
                valid = false;
            } else if (mode === 'fixed' && (isNaN(settings.fixed_amount) || settings.fixed_amount < 1)) {
                alert('Fixed amount must be at least $1');
                valid = false;
            }
            
            if (valid) {
                // Disable button during API call
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
                
                // Send API request
                fetch('/api/trading-settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(settings)
                })
                .then(response => response.json())
                .then(data => {
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-save"></i> Save';
                    
                    if (data.success) {
                        // Show success message
                        const originalText = this.innerHTML;
                        this.innerHTML = '<i class="fas fa-check"></i> Saved';
                        setTimeout(() => {
                            this.innerHTML = originalText;
                        }, 2000);
                    } else {
                        alert('Error saving settings: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error saving settings:', error);
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-save"></i> Save';
                    alert('Error saving settings. Please try again.');
                });
            }
        });
    }
}

// Update all UI components that show trading status
function updateAllTradingUIComponents(enabled) {
    const tradingToggleBtn = document.getElementById('trading-toggle-btn');
    const systemInfo = document.querySelector('.system-info');
    
    if (tradingToggleBtn) {
        if (enabled) {
            tradingToggleBtn.innerHTML = '<i class="fas fa-stop-circle"></i> Stop Trading';
            tradingToggleBtn.classList.remove('btn-success');
            tradingToggleBtn.classList.add('btn-danger');
        } else {
            tradingToggleBtn.innerHTML = '<i class="fas fa-play-circle"></i> Start Trading';
            tradingToggleBtn.classList.remove('btn-danger');
            tradingToggleBtn.classList.add('btn-success');
        }
    }
    
    if (systemInfo) {
        // Find and update the trading badge
        const tradingBadge = Array.from(systemInfo.querySelectorAll('.badge')).find(badge => 
            badge.textContent.includes('Trading Enabled') || badge.textContent.includes('Trading Disabled')
        );
        
        if (tradingBadge) {
            if (enabled) {
                tradingBadge.textContent = 'Trading Enabled';
                tradingBadge.classList.remove('badge-gray');
                tradingBadge.classList.add('badge-green');
            } else {
                tradingBadge.textContent = 'Trading Disabled';
                tradingBadge.classList.remove('badge-green');
                tradingBadge.classList.add('badge-gray');
            }
        }
    }
}

// Debug function to check signal processing
function debugSignalProcessing() {
    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            console.log("DEBUG: Checking all signals in current data");
            
            // Directly look for buy/sell signals
            let foundSignals = 0;
            Object.keys(data).forEach(symbol => {
                if (symbol.startsWith('_')) return; // Skip system keys
                
                const symbolData = data[symbol];
                if (symbolData && symbolData.signal && symbolData.signal.decision) {
                    const decision = symbolData.signal.decision.toLowerCase();
                    console.log(`DEBUG: Symbol ${symbol} has decision: ${decision}`);
                    foundSignals++;
                    
                    // If it's a buy/sell, add it to activity history if not already there
                    if (decision !== 'hold') {
                        const historyItem = {
                            symbol,
                            action: decision,
                            timestamp: symbolData.timestamp || new Date().toISOString(),
                            rsi: symbolData.rsi ? symbolData.rsi.value : null,
                            status: symbolData.result ? symbolData.result.status : null
                        };
                        
                        // Force add to history
                        window.activityHistory.unshift(historyItem);
                        console.log(`FORCE ADDED ${decision} signal for ${symbol} to activity history`);
                    }
                }
            });
            
            console.log(`DEBUG: Found ${foundSignals} total signals`);
            
            // Always update the activity log
            updateActivityLog();
        })
        .catch(error => {
            console.error('Error in debug signal check:', error);
        });
}

// Set up automatic refresh
setInterval(function() {
    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            updateDashboard(data);
            
            // Run debug signal processing after every 3rd regular update
            if (Math.random() < 0.3) {
                console.log("Running debug signal processing...");
                debugSignalProcessing();
            }
            
            // Charts are already rendered during updateDashboard
            console.log("🔄 Dashboard updated with latest data");
        })
        .catch(error => {
            console.error('Error in auto refresh:', error);
        });
}, 15000); // Refresh every 15 seconds

// Run the debug function once after 5 seconds
setTimeout(debugSignalProcessing, 5000);

// Add window resize handler to ensure charts adapt to screen size changes
window.addEventListener('resize', () => {
    // Simple debounce to avoid excessive redraws
    if (window.resizeTimeout) {
        clearTimeout(window.resizeTimeout);
    }
    window.resizeTimeout = setTimeout(() => {
        console.log("Window resized, updating chart dimensions");
        // Refresh data to trigger chart updates with new dimensions
        fetch('/api/data')
            .then(response => response.json())
            .then(data => updateDashboard(data))
            .catch(error => console.error('Error updating after resize:', error));
    }, 250);
});