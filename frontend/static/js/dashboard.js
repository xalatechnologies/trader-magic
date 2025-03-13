// Wait for DOM to be loaded
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM loaded - initializing dashboard");
    
    // Grab UI elements
    const connectionStatus = document.getElementById('connection-status');
    const refreshButton = document.getElementById('refresh-btn');
    const refreshApiButton = document.getElementById('refresh-api-btn');
    const reloadKeysButton = document.getElementById('reload-keys-btn');
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
    const closeModalBtns = document.querySelectorAll('.close-modal');
    const activityLog = document.getElementById('activity-log');
    const liquidateAllBtn = document.getElementById('liquidate-all-btn');
    const liquidationModal = document.getElementById('liquidation-modal');
    const confirmLiquidationBtn = document.getElementById('confirm-liquidation');
    const cancelLiquidationBtn = document.getElementById('cancel-liquidation');
    
    console.log("Activity log element found:", !!activityLog);
    
    // Initialize socket.io connection
    const socket = io();
    
    // MAKE ACTIVITY HISTORY GLOBAL so it's accessible everywhere
    window.activityHistory = [];
    
    // Socket events
    socket.on('connect', function() {
        connectionStatus.innerHTML = '<i class="fas fa-circle-check" style="color: green;"></i> Connected';
        
        // Register for transaction updates
        socket.emit('register_for_transaction_updates');
    });
    
    socket.on('disconnect', function() {
        connectionStatus.innerHTML = '<i class="fas fa-circle-xmark" style="color: red;"></i> Disconnected';
    });
    
    socket.on('data_update', function(data) {
        updateDashboard(data);
    });
    
    // Listen for account update events
    socket.on('account_update_needed', function() {
        console.log('Account update notification received');
        // Immediately fetch and update account data
        fetchAccountInfo().then(accountData => {
            updateAccountSummary(accountData);
            console.log('Account data updated due to transaction notification');
        }).catch(error => {
            console.error('Error updating account data:', error);
        });
    });
    
    // Listen for transaction complete events to immediately update affected cards
    socket.on('transaction_complete', function(data) {
        console.log('Transaction complete notification received:', data);
        if (data.symbol) {
            // First update account data for immediate balance changes
            fetchAccountInfo().then(accountData => {
                updateAccountSummary(accountData);
            });
            
            // Then refresh the specific card for this transaction
            refreshCard(data.symbol);
            
            // Add a notification to activity history
            window.activityHistory.unshift({
                symbol: data.symbol,
                action: data.decision || 'transaction',
                timestamp: data.timestamp || new Date().toISOString(),
                status: 'executed',
                message: `Real-time update: ${data.decision || 'Transaction'} executed for ${data.symbol}`
            });
            updateActivityLog();
        }
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
    
    // Add API refresh button handler
    if (refreshApiButton) {
        refreshApiButton.addEventListener('click', function() {
            if (!confirm('This will refresh all transactions and clear API key caches.\n\nThis helps ensure you are using the most recent API keys from your .env file.\n\nContinue?')) {
                return;
            }
            
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing...';
            
            // Add to activity history before the request
            window.activityHistory.unshift({
                timestamp: new Date().toISOString(),
                type: 'system',
                action: 'refresh',
                symbol: 'SYSTEM',
                message: 'Refreshing API data and clearing caches...'
            });
            updateActivityLog();
            
            // Call the new endpoint for refreshing all transactions
            fetch('/api/refresh_all_transactions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('API refresh response:', data);
                
                // Show a quick success message
                if (data.success) {
                    const apiKeysCleared = data.api_keys_cleared || 0;
                    this.innerHTML = '<i class="fas fa-check"></i> Done';
                    
                    // Add to activity history
                    window.activityHistory.unshift({
                        timestamp: new Date().toISOString(),
                        type: 'success',
                        action: 'refresh',
                        symbol: 'SYSTEM',
                        message: `API refresh completed: ${data.message}${apiKeysCleared > 0 ? `, cleared ${apiKeysCleared} API key cache entries` : ''}`
                    });
                    updateActivityLog();
                    
                    // Fetch all data again to update the dashboard
                    return fetch('/api/data')
                        .then(response => response.json())
                        .then(data => {
                            updateDashboard(data);
                            
                            // Also update account info explicitly
                            return fetch('/api/account')
                                .then(response => response.json())
                                .then(accountData => {
                                    updateAccountSummary(accountData);
                                    console.log('Account refreshed after API refresh');
                                })
                                .catch(error => {
                                    console.error('Error getting account data after refresh:', error);
                                });
                        });
                } else {
                    throw new Error(data.error || 'API refresh failed');
                }
            })
            .catch(error => {
                console.error('Error refreshing API:', error);
                
                // Show error state
                this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
                
                // Add error message to activity log
                window.activityHistory.unshift({
                    timestamp: new Date().toISOString(),
                    type: 'error',
                    action: 'error',
                    symbol: 'SYSTEM',
                    message: `API refresh failed: ${error.message || 'Unknown error'}`
                });
                updateActivityLog();
                
                // Alert the user
                alert(`Error refreshing API: ${error.message || 'Unknown error'}`);
            })
            .finally(() => {
                // Restore button after 2 seconds regardless of success/failure
                setTimeout(() => {
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-key"></i> Refresh API';
                }, 2000);
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
    
    // Handle modals
    if (docsBtn && helpModal) {
        docsBtn.addEventListener('click', function() {
            helpModal.classList.add('show');
        });
        
        // Handle liquidation modal
        if (liquidateAllBtn && liquidationModal) {
            liquidateAllBtn.addEventListener('click', function() {
                liquidationModal.classList.add('show');
            });
            
            confirmLiquidationBtn.addEventListener('click', function() {
                // Disable the button to prevent double-clicks
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                
                // First, stop all trading
                fetch('/api/toggle_trading', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ enabled: false })
                })
                .then(response => response.json())
                .then(() => {
                    // Then liquidate all positions
                    return fetch('/api/liquidate-all', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                })
                .then(response => response.json())
                .then(data => {
                    // Update UI components
                    updateAllTradingUIComponents(false);
                    liquidationModal.classList.remove('show');
                    
                    // Show success message
                    const message = `Successfully liquidated all positions. ${data.message || ''}`;
                    window.activityHistory.unshift({
                        timestamp: new Date().toISOString(),
                        type: 'success',
                        message: message
                    });
                    updateActivityLog();
                    
                    // Refresh account data
                    fetchAccountInfo();
                })
                .catch(error => {
                    console.error('Error during liquidation:', error);
                    window.activityHistory.unshift({
                        timestamp: new Date().toISOString(),
                        type: 'error',
                        message: `Failed to liquidate positions: ${error.message || 'Unknown error'}`
                    });
                    updateActivityLog();
                })
                .finally(() => {
                    // Re-enable the button
                    this.disabled = false;
                    this.innerHTML = 'Yes, Liquidate All Positions';
                });
            });
            
            cancelLiquidationBtn.addEventListener('click', function() {
                liquidationModal.classList.remove('show');
            });
            
            // Close when clicking outside the modal
            liquidationModal.addEventListener('click', function(e) {
                if (e.target === liquidationModal) {
                    liquidationModal.classList.remove('show');
                }
            });
        }
        
        // Close button handlers for all modals
        closeModalBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const modal = this.closest('.modal');
                if (modal) {
                    modal.classList.remove('show');
                }
            });
        });
        
        // Close help modal when clicking outside
        helpModal.addEventListener('click', function(e) {
            if (e.target === helpModal) {
                helpModal.classList.remove('show');
            }
        });
    }
    
    // Initialize trade settings
    // Define the initTradeSettings function inside the DOMContentLoaded scope
    function initTradeSettings() {
        console.log('Initializing trade settings');
        if (tradeModeSelect) {
            console.log('Trade mode select found:', tradeModeSelect);
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
            console.log('Save button found:', saveTradeSettingsBtn);
            saveTradeSettingsBtn.addEventListener('click', function() {
                console.log('Save button clicked');
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
                        
                        if (data.status === 'success') {
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
    
    // Call the function
    initTradeSettings();

    // Add reload API keys button handler
    if (reloadKeysButton) {
        reloadKeysButton.addEventListener('click', function() {
            if (!confirm('This will reload API keys from your .env file and clear any cached keys. Continue?')) {
                return;
            }
            
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Reloading Keys...';
            
            // Call the reloadApiKeys function
            reloadApiKeys()
                .then(() => {
                    // Show success indicator
                    this.innerHTML = '<i class="fas fa-check"></i> Keys Reloaded';
                    
                    // Restore button after 2 seconds
                    setTimeout(() => {
                        this.disabled = false;
                        this.innerHTML = '<i class="fas fa-file-code"></i> Use .env Keys';
                    }, 2000);
                })
                .catch(error => {
                    console.error('Error reloading API keys:', error);
                    
                    // Show error state
                    this.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error';
                    
                    // Restore button after 2 seconds
                    setTimeout(() => {
                        this.disabled = false;
                        this.innerHTML = '<i class="fas fa-file-code"></i> Use .env Keys';
                    }, 2000);
                });
        });
    }
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
    const chartContainer = document.getElementById(`chart-container-${symbolKey}`);
    
    // Check if this symbol is valid for Alpaca
    const isAlpacaInvalidSymbol = data.alpaca_valid === false;
    
    // If the symbol is invalid for Alpaca, update the UI accordingly
    if (isAlpacaInvalidSymbol) {
        // Add a red border to the card
        card.classList.add('alpaca-invalid-symbol');
        
        // Clear RSI, decision, and status values
        rsiElement.textContent = '--';
        decisionElement.textContent = '--';
        decisionElement.className = 'metric-value decision';
        statusElement.textContent = '--';
        
        // Disable the chart container
        if (chartContainer) {
            chartContainer.classList.add('disabled-chart');
        }
        
        // Display a message about Alpaca not supporting this symbol
        tradeInfoElement.innerHTML = `
            <div class="trade-details trade-failed">
                <strong>Symbol not supported:</strong> Alpaca does not support ${symbol}
            </div>
        `;
        
        // Update the timestamp if available
        if (data.timestamp) {
            updatedElement.textContent = `Updated ${getTimeAgo(data.timestamp)}`;
        } else {
            updatedElement.textContent = 'No data';
        }
        
        return; // Exit early to avoid further processing
    } else {
        // Remove the invalid class if it was previously added
        card.classList.remove('alpaca-invalid-symbol');
        
        // Enable the chart container
        if (chartContainer) {
            chartContainer.classList.remove('disabled-chart');
        }
    }
    
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
    
    // Update price chart (only if the symbol is valid for Alpaca)
    if (!isAlpacaInvalidSymbol) {
        updatePriceChart(symbolKey, data);
    }
    
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
        const normalizedSymbol = normalizeSymbol(symbol);
        const historyItem = {
            symbol: normalizedSymbol,
            action,
            timestamp,
            rsi: data.rsi ? data.rsi.value : null,
            status: data.result ? data.result.status : null
        };
        
        console.log(`Adding to activity history: ${normalizedSymbol} ${action} (${historyItem.status || 'no status'})`);
        
        // Check if this event is already in the history
        const isDuplicate = window.activityHistory.some(item => 
            normalizeSymbol(item.symbol) === normalizedSymbol && 
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
        // Skip invalid items
        if (!item || typeof item !== 'object') return;
        
        const time = formatTimestamp(item.timestamp || new Date().toISOString());
        
        let icon;
        if (item.action === 'buy') {
            icon = '<i class="fas fa-arrow-up"></i>';
        } else if (item.action === 'sell') {
            icon = '<i class="fas fa-arrow-down"></i>';
        } else {
            icon = '<i class="fas fa-minus"></i>';
        }
        
        // Add RSI value if available
        const rsiText = item.rsi !== undefined && item.rsi !== null ? `RSI: ${item.rsi.toFixed(2)}` : '';
        
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
            <div class="activity-item ${item.action || 'unknown'}">
                ${icon}
                <div class="activity-details">
                    <strong>${item.symbol || 'Unknown'}</strong> 
                    <span class="activity-action">${item.action ? item.action.toUpperCase() : 'ACTION'}</span>
                    ${rsiText ? `<span class="activity-rsi">(${rsiText})</span>` : ''}
                    ${statusBadge}
                </div>
                <span class="activity-timestamp" title="${time}">${time}</span>
            </div>
        `;
    });
    
    activityLog.innerHTML = html;
}

// Function to fetch account information from the API
function fetchAccountInfo() {
    console.log('Fetching account info...');
    return fetch('/api/account')
        .then(response => {
            console.log('Account info response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Account info received:', data);
            console.log('Positions in account data:', JSON.stringify(data.positions));
            return data;
        })
        .catch(error => {
            console.error('Error fetching account info:', error);
            return {
                error: 'Failed to fetch account data',
                cash: 0,
                portfolio_value: 0,
                buying_power: 0,
                positions: []
            };
        });
}

// Function to update the account summary UI with the fetched data
function updateAccountSummary(accountData) {
    console.log('Updating account summary with data:', accountData);
    
    // Update account type badge
    const accountTypeBadge = document.getElementById('account-type-badge');
    if (accountTypeBadge) {
        const isPaperTrading = accountData.paper_trading;
        accountTypeBadge.textContent = isPaperTrading ? 'Paper Trading' : 'Live Trading';
        accountTypeBadge.className = 'account-type-badge ' + (isPaperTrading ? 'paper' : 'live');
    }
    
    // Update account metrics
    document.getElementById('portfolio-value').textContent = '$' + parseFloat(accountData.portfolio_value || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    // Update daily change with color coding
    const dailyChangeElement = document.getElementById('daily-change');
    
    // Apply reasonable limits to daily change values to prevent extreme calculations
    let dailyChange = parseFloat(accountData.daily_change || 0);
    let dailyChangePercent = parseFloat(accountData.daily_change_percent || 0);
    
    // Calculate a reasonable maximum change based on portfolio value
    const portfolioValue = parseFloat(accountData.portfolio_value || 0);
    const maxReasonableChange = portfolioValue * 0.15; // 15% as maximum reasonable daily change
    
    // Cap the daily change amount if it seems unreasonably high
    if (Math.abs(dailyChange) > maxReasonableChange && portfolioValue > 0) {
        console.warn(`Daily change of ${dailyChange} seems unreasonable compared to portfolio value ${portfolioValue}. Capping at 15%.`);
        // Cap the daily change while preserving the sign
        dailyChange = dailyChange > 0 ? maxReasonableChange : -maxReasonableChange;
        
        // Recalculate the percentage
        dailyChangePercent = dailyChange / portfolioValue * 100;
    }
    
    // Format the daily change with sign and percentage
    let formattedValue;
    if (dailyChange >= 0) {
        formattedValue = `+$${dailyChange.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} (+${Math.abs(dailyChangePercent).toFixed(2)}%)`;
    } else {
        formattedValue = `-$${Math.abs(dailyChange).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} (-${Math.abs(dailyChangePercent).toFixed(2)}%)`;
    }
    dailyChangeElement.textContent = formattedValue;
    
    // Add color class based on positive or negative change
    if (dailyChange > 0) {
        dailyChangeElement.className = 'metric-value positive';
        dailyChangeElement.style.color = 'var(--success)';
    } else if (dailyChange < 0) {
        dailyChangeElement.className = 'metric-value negative';
        dailyChangeElement.style.color = 'var(--danger)';
    } else {
        dailyChangeElement.className = 'metric-value';
    }
    
    document.getElementById('cash-balance').textContent = '$' + parseFloat(accountData.cash || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('buying-power').textContent = '$' + parseFloat(accountData.buying_power || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    
    // Update position information in each symbol card
    const positions = accountData.positions || [];
    console.log('Positions to display:', positions);
    
    // Get all symbols from the UI
    const symbolCards = document.querySelectorAll('.symbol-card');
    console.log('Found symbol cards:', symbolCards.length);
    
    // First, reset all position displays to show default values
    symbolCards.forEach(card => {
        const cardId = card.id;
        const symbol = cardId.replace('card-', '');
        console.log('Setting default position display for symbol:', symbol);
        
        // Get the position elements
        const qtyElement = document.getElementById(`position-qty-${symbol}`);
        const valueElement = document.getElementById(`position-value-${symbol}`);
        const plElement = document.getElementById(`position-pl-${symbol}`);
        const positionInfo = document.getElementById(`position-info-${symbol}`);
        
        console.log('Position elements found:', {
            symbol,
            qtyElement: !!qtyElement,
            valueElement: !!valueElement,
            plElement: !!plElement,
            positionInfo: !!positionInfo
        });
        
        // Set default values (no position)
        if (qtyElement) qtyElement.textContent = '0';
        if (valueElement) valueElement.textContent = '$0.00';
        if (plElement) {
            plElement.textContent = '$0.00';
            plElement.className = 'metric-value'; // Remove any positive/negative class
        }
        
        // Add a subtle indicator that there's no position
        if (qtyElement && valueElement && plElement) {
            qtyElement.classList.add('no-position');
            valueElement.classList.add('no-position');
            plElement.classList.add('no-position');
        }
        
        // Make sure position info is always visible
        if (positionInfo) {
            // Remove the no-position class if it exists
            positionInfo.classList.remove('no-position');
            // Force display
            positionInfo.style.display = 'block';
        }
    });
    
    // Then update cards for symbols that have positions
    positions.forEach(position => {
        console.log('Processing position for symbol:', position.symbol);
        
        // Convert Alpaca symbol format to our format
        const alpacaSymbol = position.symbol;
        
        // Handle different symbol formats (e.g., BTC/USD vs BTCUSD)
        let possibleSymbols = [];
        
        // Special case handling for common crypto symbols from Alpaca
        // The key issue is that Alpaca returns USD but our frontend uses USDT
        if (alpacaSymbol === 'BTCUSD') {
            possibleSymbols.push(
                'BTCUSD',
                'BTC/USD',
                'BTC/USDT',  // This is what's in our .env file
                'BTC-USD',
                'BTC-USDT'
            );
            console.log('Special case for BTCUSD -> trying BTC/USDT');
        } else if (alpacaSymbol === 'ETHUSD') {
            possibleSymbols.push(
                'ETHUSD',
                'ETH/USD',
                'ETH/USDT',  // This is what's in our .env file
                'ETH-USD',
                'ETH-USDT'
            );
            console.log('Special case for ETHUSD -> trying ETH/USDT');
        } else if (alpacaSymbol === 'DOGEUSD') {
            possibleSymbols.push(
                'DOGEUSD',
                'DOGE/USD',
                'DOGE/USDT',  // This is what's in our .env file
                'DOGE-USD',
                'DOGE-USDT'
            );
            console.log('Special case for DOGEUSD -> trying DOGE/USDT');
        }
        // For crypto symbols like BTCUSD, we need to try both BTCUSD and BTC/USD formats
        else if (alpacaSymbol.endsWith('USD')) {
            const base = alpacaSymbol.replace('USD', '');
            possibleSymbols.push(
                alpacaSymbol,           // BTCUSD
                `${base}/USD`,         // BTC/USD
                `${base}-USD`          // BTC-USD
            );
        } else if (alpacaSymbol.includes('/')) {
            // For symbols with slashes, try both with and without slash
            const noSlash = alpacaSymbol.replace('/', '');
            possibleSymbols.push(
                alpacaSymbol,           // BTC/USD
                noSlash,               // BTCUSD
                alpacaSymbol.replace('/', '-') // BTC-USD
            );
        } else {
            // For other symbols, just use as is
            possibleSymbols.push(alpacaSymbol);
        }
        
        console.log('Possible symbol formats for', alpacaSymbol, ':', possibleSymbols);
        
        // Find the matching symbol card
        let found = false;
        
        // Try each possible symbol format
        for (const sym of possibleSymbols) {
            // Normalize the symbol for DOM ID (replace / with -)
            const normalizedSymbol = sym.replace('/', '-');
            console.log('Checking for normalized symbol:', normalizedSymbol);
            
            // Get the position elements
            const qtyElement = document.getElementById(`position-qty-${normalizedSymbol}`);
            const valueElement = document.getElementById(`position-value-${normalizedSymbol}`);
            const plElement = document.getElementById(`position-pl-${normalizedSymbol}`);
            const positionInfo = document.getElementById(`position-info-${normalizedSymbol}`);
            
            console.log('Elements for', normalizedSymbol, ':', {
                qtyElement: !!qtyElement,
                valueElement: !!valueElement,
                plElement: !!plElement,
                positionInfo: !!positionInfo
            });
            
            // If we found all the elements, update them
            if (qtyElement && valueElement && plElement) {
                console.log('Found matching elements for symbol:', normalizedSymbol);
                found = true;
                
                // Get the position data
                const quantity = parseFloat(position.quantity || 0);
                const marketValue = parseFloat(position.market_value || 0);
                const unrealizedPL = parseFloat(position.unrealized_pl || 0);
                
                // Determine if P/L is positive or negative
                const plClass = unrealizedPL >= 0 ? 'positive' : 'negative';
                const plPrefix = unrealizedPL >= 0 ? '+' : '';
                
                // Remove the no-position class
                qtyElement.classList.remove('no-position');
                valueElement.classList.remove('no-position');
                plElement.classList.remove('no-position');
                
                // Update the position information
                qtyElement.textContent = quantity.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 8});
                valueElement.textContent = '$' + marketValue.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                plElement.textContent = `${plPrefix}$${Math.abs(unrealizedPL).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                plElement.className = `metric-value ${plClass}`;
                
                // Make sure position info is visible
                if (positionInfo) {
                    console.log('Showing position info for:', normalizedSymbol);
                    positionInfo.classList.remove('no-position');
                    positionInfo.style.display = 'block';
                }
                
                // We found a match, no need to check other formats
                break;
            }
        }
        
        if (!found) {
            console.log('Could not find matching symbol card for position:', position.symbol);
        }
    });
}

// Add global variable to store news history
window.newsItems = [];

// Add a new function to update the news feed
function updateNewsFeed(newsData) {
    const newsFeed = document.getElementById('news-feed');
    
    if (!newsFeed) {
        console.error("News feed element not found!");
        return;
    }
    
    if (!newsData || newsData.length === 0) {
        console.log("No news data available, showing empty feed message");
        newsFeed.innerHTML = '<div class="empty-log">No recent news</div>';
        return;
    }
    
    console.log(`Updating news feed with ${newsData.length} items`);
    
    let html = '';
    newsData.forEach(item => {
        // Skip invalid items
        if (!item || typeof item !== 'object') return;
        
        const time = formatTimestamp(item.timestamp || new Date().toISOString());
        
        // Ensure item.symbols exists and is an array before using join
        const symbols = Array.isArray(item.symbols) ? item.symbols.join(', ') : 'Unknown';
        
        const headline = item.headline || 'No headline';
        const url = item.url || '#';
        const source = item.source || 'Alpaca';
        
        // Create a clickable headline if URL is available
        const headlineHtml = url && url !== '#' 
            ? `<a href="${url}" target="_blank" class="news-headline">${headline} <i class="fas fa-external-link-alt"></i></a>` 
            : `<span class="news-headline">${headline}</span>`;

        html += `
            <div class="news-item">
                <i class="fas fa-newspaper"></i>
                <div class="news-details">
                    ${headlineHtml}
                    <div class="news-meta">
                        <span class="news-symbols">${symbols}</span>
                        <span class="news-source">Source: ${source}</span>
                        <span class="news-time">${time}</span>
                    </div>
                </div>
            </div>
        `;
    });
    
    newsFeed.innerHTML = html;
}

// Add this helper function near the top of the file, after the document load event
function normalizeSymbol(symbol) {
    // Handle various symbol formats (BTC/USD, BTC/USDT, BTCUSD, etc)
    if (!symbol) return symbol;
    
    // If it's already in the preferred format (with slash), return it
    if (symbol.includes('/')) {
        // Convert BTC/USD to BTC/USDT if needed
        if (symbol.endsWith('/USD')) {
            return symbol.replace('/USD', '/USDT');
        }
        return symbol;
    }
    
    // Handle BTCUSD, ETHUSD format
    if (symbol.endsWith('USD')) {
        const base = symbol.slice(0, -3);
        return `${base}/USDT`;
    }
    
    // Handle BTCUSDT format
    if (symbol.endsWith('USDT')) {
        const base = symbol.slice(0, -4);
        return `${base}/USDT`;
    }
    
    // For other formats, just return as is
    return symbol;
}

function updateDashboard(data) {
    // Store the last received data for force-redrawing without server refresh
    window.lastReceivedData = data;
    
    // Get trading status but DON'T clear executed trades
    // This allows us to show trade history in Recent Activity
    const tradingEnabled = data.trading_enabled;
    
    // Update Ollama status if present
    if (data.ollama_status) {
        updateOllamaStatus(data.ollama_status);
    }
    
    // Update trading enabled status in UI if provided
    if (data.trading_enabled !== undefined) {
        console.log("Trading enabled status from server:", tradingEnabled);
        
        // Use centralized function to update all trading UI components
        updateAllTradingUIComponents(tradingEnabled);
    }
    
    // DIAGNOSTIC: Check what data we're getting
    console.log("RECEIVED DATA UPDATE:", Object.keys(data));
    
    // Update news feed if data is available
    if (data.recent_news) {
        console.log("Received news data:", data.recent_news);
        window.newsItems = data.recent_news;
        updateNewsFeed(window.newsItems);
    }
    
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
    
    // Fetch and update account information
    fetchAccountInfo().then(accountData => {
        updateAccountSummary(accountData);
    });
    
    // Update each symbol card - with extra diagnostics
    Object.keys(data).forEach(symbol => {
        if (symbol !== '_system' && symbol !== '_debug' && symbol !== '_trade_results' && 
            symbol !== 'recent_news' && symbol !== 'trading_enabled' && 
            symbol !== 'ollama_status' && symbol !== 'account') {
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

    // Explicitly populate activity history from all signals in data
    console.log("Populating activity history from initial data load");
    Object.keys(data).forEach(symbol => {
        if (symbol.startsWith('_')) return; // Skip system keys
        
        const symbolData = data[symbol];
        if (symbolData && symbolData.signal && symbolData.signal.decision) {
            // Only add buy/sell decisions (skip hold)
            const decision = symbolData.signal.decision.toLowerCase();
            if (decision !== 'hold') {
                const normalizedSymbol = normalizeSymbol(symbol);
                const historyItem = {
                    symbol: normalizedSymbol,
                    action: decision,
                    timestamp: symbolData.timestamp || new Date().toISOString(),
                    rsi: symbolData.rsi ? symbolData.rsi.value : null,
                    status: symbolData.result ? symbolData.result.status : null
                };
                
                // Force add to history
                window.activityHistory.unshift(historyItem);
                console.log(`FORCE ADDED ${decision} signal for ${normalizedSymbol} to activity history`);
            }
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
        // Also fetch account data on initial load
        fetchAccountInfo().then(accountData => {
            updateAccountSummary(accountData);
        });
        updateDashboard(data);
        
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

// Note: initTradeSettings function has been moved inside the DOMContentLoaded event handler

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
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
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
                        const normalizedSymbol = normalizeSymbol(symbol);
                        const historyItem = {
                            symbol: normalizedSymbol,
                            action: decision,
                            timestamp: symbolData.timestamp || new Date().toISOString(),
                            rsi: symbolData.rsi ? symbolData.rsi.value : null,
                            status: symbolData.result ? symbolData.result.status : null
                        };
                        
                        // Force add to history
                        window.activityHistory.unshift(historyItem);
                        console.log(`FORCE ADDED ${decision} signal for ${normalizedSymbol} to activity history`);
                    }
                }
            });
            
            console.log(`DEBUG: Found ${foundSignals} total signals`);
            
            // Always update the activity log
            updateActivityLog();
        })
        .catch(error => {
            console.error('Error in debug signal check:', error);
            
            // Add error to activity history to make it visible
            window.activityHistory.unshift({
                timestamp: new Date().toISOString(),
                symbol: 'DEBUG',
                action: 'error',
                message: `Debug signal check failed: ${error.message || 'Unknown error'}`
            });
            updateActivityLog();
        });
}

// Set up automatic refresh - changed from 15 seconds to 2 minutes (120000ms)
setInterval(function() {
    console.log("Performing scheduled 2-minute refresh...");
    // Refresh account data
    fetchAccountInfo().then(accountData => {
        updateAccountSummary(accountData);
    });
    
    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            updateDashboard(data);
            console.log("🔄 Dashboard updated with latest data (2-minute refresh)");
        })
        .catch(error => {
            console.error('Error in auto refresh:', error);
        });
}, 120000); // Refresh every 2 minutes (120000ms) instead of 15 seconds

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

// Function to refresh a single card manually - helpful for debugging
async function refreshCard(symbol) {
    console.log(`Manual refresh requested for card: ${symbol}`);
    
    try {
        // Get the button that was clicked and show loading state
        const symbolKey = symbol.replace('/', '-');
        const refreshBtn = document.querySelector(`#card-${symbolKey} .refresh-card-btn`);
        if (refreshBtn) {
            refreshBtn.innerHTML = '⏳';
            refreshBtn.disabled = true;
        }
        
        // First, try to refresh just the trade result
        const tradeRefreshResponse = await fetch(`/api/refresh_trade/${encodeURIComponent(symbol)}`);
        const tradeData = await tradeRefreshResponse.json();
        
        if (tradeData.success && tradeData.result) {
            console.log(`Successfully refreshed trade result for ${symbol}:`, tradeData.result);
        } else {
            console.warn(`No trade result found for ${symbol} in refresh`);
        }
        
        // Then fetch all data to update the card
        const response = await fetch('/api/data');
        const data = await response.json();
        
        // Check if we have data for this symbol
        if (data[symbol]) {
            console.log(`Refreshing card for ${symbol} with data:`, data[symbol]);
            
            // If we got a trade result directly, make sure it's in the data
            if (tradeData.success && tradeData.result) {
                // Update the data to include the refreshed trade result
                data[symbol].result = tradeData.result;
                console.log(`Updated ${symbol} data with fresh trade result`);
            }
            
            // Check specifically if we have a trade result
            if (data[symbol].result) {
                console.log(`Found trade result for ${symbol}:`, data[symbol].result);
            } else {
                console.warn(`No trade result found for ${symbol} in refresh`);
            }
            
            // Update the card
            updateSymbolCard(symbol, data[symbol]);
            
            // Show success indicator
            if (refreshBtn) {
                refreshBtn.innerHTML = '✅';
                setTimeout(() => {
                    refreshBtn.innerHTML = '🔄';
                    refreshBtn.disabled = false;
                }, 1000);
            }
        } else {
            console.error(`No data found for ${symbol} in refresh`);
            
            // Show error indicator
            if (refreshBtn) {
                refreshBtn.innerHTML = '❌';
                setTimeout(() => {
                    refreshBtn.innerHTML = '🔄';
                    refreshBtn.disabled = false;
                }, 1000);
            }
        }
    } catch (error) {
        console.error(`Error refreshing card for ${symbol}:`, error);
        
        // Get the button that was clicked and show error state
        const symbolKey = symbol.replace('/', '-');
        const refreshBtn = document.querySelector(`#card-${symbolKey} .refresh-card-btn`);
        if (refreshBtn) {
            refreshBtn.innerHTML = '❌';
            setTimeout(() => {
                refreshBtn.innerHTML = '🔄';
                refreshBtn.disabled = false;
            }, 1000);
        }
    }
}

// Make the refresh buttons visible in dev mode
document.addEventListener('keydown', function(event) {
    // Ctrl+Shift+D to toggle debug mode
    if (event.ctrlKey && event.shiftKey && event.key === 'D') {
        const refreshBtns = document.querySelectorAll('.refresh-card-btn');
        refreshBtns.forEach(btn => {
            btn.style.display = btn.style.display === 'none' ? 'inline-block' : 'none';
        });
        console.log('Debug refresh buttons toggled');
    }
});

// Add a separate function to specifically reload API keys from .env file
async function reloadApiKeys() {
    console.log('Reloading API keys from .env file...');
    
    try {
        // Show loading message in activity log
        window.activityHistory.unshift({
            timestamp: new Date().toISOString(),
            type: 'system',
            action: 'info',
            symbol: 'SYSTEM',
            message: 'Reloading API keys from .env file...'
        });
        updateActivityLog();
        
        // Call the API endpoint to reload keys
        const response = await fetch('/api/reload_api_keys', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Successfully reloaded API keys:', data);
            
            // Add success message to activity history
            window.activityHistory.unshift({
                timestamp: new Date().toISOString(),
                type: 'success',
                action: 'reload_keys',
                symbol: 'SYSTEM',
                message: `API keys reloaded: ${data.message}`
            });
            updateActivityLog();
            
            // Show confirmation dialog
            const message = `API keys have been reloaded from .env file.\n\nFor changes to take full effect, consider restarting the trade_execution service:\ndocker restart trade_execution`;
            alert(message);
            
            // Refresh data after reloading keys
            return fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    updateDashboard(data);
                    console.log('Dashboard updated after API key reload');
                    return data;
                });
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Error reloading API keys:', error);
        
        // Add error message to activity history
        window.activityHistory.unshift({
            timestamp: new Date().toISOString(),
            type: 'error',
            action: 'error',
            symbol: 'SYSTEM',
            message: `API key reload failed: ${error.message || 'Unknown error'}`
        });
        updateActivityLog();
        
        alert(`Error reloading API keys: ${error.message || 'Unknown error'}`);
    }
}