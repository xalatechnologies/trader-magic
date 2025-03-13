// Trading Strategies Management
(function() {
    // DOM Elements
    const strategiesContainer = document.getElementById('strategies-container');
    const strategiesList = document.getElementById('strategies-list');
    const strategiesStatusText = document.getElementById('strategies-status-text');
    const startStrategiesBtn = document.getElementById('start-strategies-btn');
    const stopStrategiesBtn = document.getElementById('stop-strategies-btn');
    const restartStrategiesBtn = document.getElementById('restart-strategies-btn');
    
    // Variables
    let strategies = [];
    let strategyManagerRunning = false;
    let isRestarting = false; // Track restart in progress
    
    // Initialize strategies
    function initializeStrategies() {
        if (!strategiesContainer) {
            console.warn('Strategy container not found in DOM');
            return;
        }
        
        console.log('Initializing strategies section');
        
        // First check the health of the strategy manager
        checkStrategyManagerHealth();
        
        // Also check the backend heartbeat
        checkBackendHeartbeat();
        
        fetchStrategies();
        fetchSignals();
        
        // Set up event listeners
        if (startStrategiesBtn) {
            startStrategiesBtn.addEventListener('click', startStrategyManager);
        }
        
        if (stopStrategiesBtn) {
            stopStrategiesBtn.addEventListener('click', stopStrategyManager);
        }
        
        if (restartStrategiesBtn) {
            restartStrategiesBtn.addEventListener('click', restartStrategyManager);
        }
        
        // Set up automatic refresh
        setInterval(checkStrategyManagerHealth, 15000); // Every 15 seconds
        setInterval(checkBackendHeartbeat, 30000);      // Every 30 seconds
        setInterval(fetchStrategies, 30000);            // Every 30 seconds
        setInterval(fetchSignals, 15000);               // Every 15 seconds
    }
    
    // Check the health of the strategy manager
    function checkStrategyManagerHealth() {
        // Don't check if a restart is in progress
        if (isRestarting) {
            console.log('Skipping health check during restart');
            return;
        }
        
        fetch('/api/strategy_manager/health')
            .then(response => response.json())
            .then(data => {
                console.log('Strategy manager health:', data);
                
                // Update the UI based on health status
                if (data.status === 'healthy') {
                    strategyManagerRunning = data.strategy_manager_running;
                    updateManagerButtons();
                    
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML = `<i class="fas fa-check-circle" style="color: var(--success);"></i> ${data.message}`;
                    }
                } else if (data.status === 'limited') {
                    // Manager registered strategies but may not be running
                    strategyManagerRunning = false;
                    updateManagerButtons();
                    
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-circle" style="color: var(--warning);"></i> ${data.message}`;
                    }
                } else if (data.status === 'error') {
                    // Error in health check
                    strategyManagerRunning = false;
                    updateManagerButtons();
                    
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML = `
                            <i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> 
                            ${data.message}
                            <button id="inline-reset-btn" class="btn btn-small btn-danger" style="margin-left: 10px;">Reset</button>
                        `;
                        
                        // Add event listener to the inline reset button
                        const inlineResetBtn = document.getElementById('inline-reset-btn');
                        if (inlineResetBtn) {
                            inlineResetBtn.addEventListener('click', resetStrategyManager);
                        }
                    }
                } else {
                    // Manager not detected
                    strategyManagerRunning = false;
                    updateManagerButtons();
                    
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML = `<i class="fas fa-info-circle" style="color: var(--info);"></i> ${data.message}`;
                    }
                }
            })
            .catch(error => {
                console.error('Error checking strategy manager health:', error);
                strategyManagerRunning = false;
                updateManagerButtons();
                
                if (strategiesStatusText) {
                    strategiesStatusText.innerHTML = `
                        <i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> 
                        Failed to check strategy manager health
                        <button id="inline-reset-btn" class="btn btn-small btn-danger" style="margin-left: 10px;">Reset</button>
                    `;
                    
                    // Add event listener to the inline reset button
                    const inlineResetBtn = document.getElementById('inline-reset-btn');
                    if (inlineResetBtn) {
                        inlineResetBtn.addEventListener('click', resetStrategyManager);
                    }
                }
            });
    }
    
    // Check the backend heartbeat
    function checkBackendHeartbeat() {
        // Don't check if a restart is in progress
        if (isRestarting) {
            console.log('Skipping backend heartbeat check during restart');
            return;
        }
        
        fetch('/api/backend/heartbeat')
            .then(response => response.json())
            .then(data => {
                console.log('Backend heartbeat:', data);
                
                // If backend is alive, update the status
                if (data.status === 'alive') {
                    // Get detailed strategy manager status
                    const strategyManagerStatus = data.strategy_manager_status;
                    const strategyDetails = data.heartbeat.strategy_manager.details;
                    
                    // Update UI based on the detailed status
                    if (strategyManagerStatus === 'running') {
                        strategyManagerRunning = true;
                        updateManagerButtons();
                        
                        // Check if the manager is stalled
                        if (strategyDetails.status === 'stalled') {
                            if (strategiesStatusText) {
                                strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i> Strategy manager appears stalled`;
                                strategiesStatusText.innerHTML += ` <small>(${strategyDetails.status_message})</small>`;
                            }
                            showNotification('Strategy manager may be stalled. Restart recommended.', 'warning');
                        }
                    }
                    
                    // Show detailed status in the tooltip if we have status
                    if (strategiesStatusText && strategyDetails.status) {
                        const statusTitle = strategiesStatusText.innerHTML;
                        if (!statusTitle.includes('data-toggle="tooltip"')) {
                            strategiesStatusText.setAttribute('data-toggle', 'tooltip');
                            strategiesStatusText.setAttribute('data-placement', 'top');
                            strategiesStatusText.setAttribute('title', strategyDetails.status_message || 'No status details available');
                        }
                    }
                    
                    // If we have strategy names but strategy manager isn't running,
                    // we might want to show that in the UI
                    if (strategyManagerStatus !== 'running' && 
                        data.heartbeat.data_clients.websocket_client) {
                        // We have some backend services but strategy manager isn't running correctly
                        if (strategiesStatusText) {
                            strategiesStatusText.innerHTML = `<i class="fas fa-info-circle" style="color: var(--warning);"></i> Backend active, strategy manager not running`;
                        }
                    }
                } else if (data.status === 'error') {
                    // Show error in console but don't update UI - let the strategy health check handle that
                    console.error('Backend heartbeat error:', data.message);
                }
            })
            .catch(error => {
                console.error('Error checking backend heartbeat:', error);
                // No need to show this error to the user, we'll just retry later
            });
    }
    
    // Fetch available strategies
    function fetchStrategies() {
        console.log('Fetching strategies...');
        fetch('/api/strategies')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error fetching strategies:', data.error);
                    strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> ${data.error}`;
                    
                    // Show the error in the strategies list as well
                    if (strategiesList) {
                        strategiesList.innerHTML = `
                            <div class="empty-strategies">
                                <p>${data.error}</p>
                                <p>The strategy manager might be running in a different container and not directly accessible from the frontend. 
                                Strategy commands will be sent via Redis.</p>
                                <button id="reset-strategy-manager-btn" class="btn btn-danger">
                                    <i class="fas fa-exclamation-triangle"></i> Emergency Reset
                                </button>
                            </div>
                        `;
                        
                        // Attach event listener to the reset button
                        const resetBtn = document.getElementById('reset-strategy-manager-btn');
                        if (resetBtn) {
                            resetBtn.addEventListener('click', resetStrategyManager);
                        }
                    }
                    return;
                }
                
                strategies = data.strategies || [];
                updateStrategiesUI();
                
                // Handle container mode communication
                if (data.container_mode) {
                    console.log('Container mode detected, using Redis for communication');
                    
                    if (strategies.length === 0 && data.status === "waiting_for_backend") {
                        // Backend container might not be running yet
                        if (strategiesStatusText) {
                            strategiesStatusText.innerHTML = `<i class="fas fa-sync-alt fa-spin" style="color: var(--info);"></i> Waiting for backend...`;
                        }
                        
                        if (strategiesList) {
                            strategiesList.innerHTML = `
                                <div class="empty-strategies">
                                    <p><i class="fas fa-info-circle"></i> ${data.message || "Waiting for the backend service to start"}</p>
                                    <p>The application is running in container mode and using Redis for inter-service communication.</p>
                                    <p>This is normal in containerized deployments. Strategy commands will still work once the backend is available.</p>
                                </div>
                            `;
                        }
                    } else {
                        // Backend container is running, strategies available via Redis
                        if (strategiesStatusText) {
                            strategiesStatusText.innerHTML = `<i class="fas fa-check-circle" style="color: var(--success);"></i> Using Redis for strategy communication`;
                        }
                    }
                } else {
                    // Direct communication mode
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML = `<i class="fas fa-check-circle" style="color: var(--success);"></i> Connected to strategy manager`;
                    }
                }
                
                // Check if there's a note in the response (indicating Redis was used)
                if (data.note) {
                    console.log('Note from strategies API:', data.note);
                    if (strategiesStatusText) {
                        strategiesStatusText.innerHTML += ` <small>(${data.note})</small>`;
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching strategies:', error);
                strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> Failed to fetch strategies`;
                
                // Show the error in the strategies list as well
                if (strategiesList) {
                    strategiesList.innerHTML = `
                        <div class="empty-strategies">
                            <p>Error connecting to the strategy API: ${error.message}</p>
                            <p>Please check if the server is running.</p>
                        </div>
                    `;
                }
            });
    }
    
    // Fetch trading signals
    function fetchSignals() {
        console.log('Fetching trading signals...');
        fetch('/api/signals')
            .then(response => response.json())
            .then(data => {
                updateSignalsUI(data.signals || []);
            })
            .catch(error => {
                console.error('Error fetching signals:', error);
            });
    }
    
    // Update strategies UI
    function updateStrategiesUI() {
        if (!strategiesList) return;
        
        if (strategies.length === 0) {
            strategiesList.innerHTML = '<div class="empty-strategies">No strategies available</div>';
            strategiesStatusText.innerHTML = '<i class="fas fa-info-circle" style="color: var(--warning);"></i> No strategies configured';
            return;
        }
        
        let html = '';
        strategies.forEach(strategy => {
            html += `
                <div class="strategy-card" id="strategy-${strategy.class}" data-strategy="${strategy.class}">
                    <div class="strategy-info">
                        <div class="strategy-name">${strategy.name}</div>
                        <div class="strategy-description">${strategy.description || 'No description available'}</div>
                    </div>
                    <div class="strategy-controls">
                        <div class="strategy-status ${strategy.enabled ? 'enabled' : 'disabled'}">
                            ${strategy.enabled ? 'Enabled' : 'Disabled'}
                        </div>
                        <label class="strategy-toggle">
                            <input type="checkbox" class="strategy-toggle-input" 
                                data-strategy="${strategy.class}" 
                                ${strategy.enabled ? 'checked' : ''}>
                            <span class="strategy-toggle-slider"></span>
                            <span class="strategy-loading-indicator"><i class="fas fa-circle-notch fa-spin"></i></span>
                        </label>
                    </div>
                </div>
            `;
        });
        
        strategiesList.innerHTML = html;
        strategiesStatusText.innerHTML = `<i class="fas fa-check-circle" style="color: var(--success);"></i> ${strategies.length} strategies available`;
        
        // Add event listeners to toggle switches
        document.querySelectorAll('.strategy-toggle-input').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const strategyClass = this.dataset.strategy;
                const enabled = this.checked;
                
                updateStrategyStatus(strategyClass, enabled);
            });
        });
    }
    
    // Update signals UI 
    function updateSignalsUI(signals) {
        if (signals.length === 0) return;
        
        // Check if signals section exists, if not create it
        let signalsSection = document.getElementById('strategy-signals-section');
        if (!signalsSection) {
            signalsSection = document.createElement('div');
            signalsSection.id = 'strategy-signals-section';
            signalsSection.className = 'strategy-signals';
            signalsSection.innerHTML = `
                <div class="strategy-signals-header">
                    <h4>Recent Trading Signals</h4>
                    <span id="signals-count">${signals.length} signals</span>
                </div>
                <div class="signal-list" id="signal-list"></div>
            `;
            
            if (strategiesContainer) {
                strategiesContainer.appendChild(signalsSection);
            }
        } else {
            // Update the count
            const signalsCount = document.getElementById('signals-count');
            if (signalsCount) {
                signalsCount.textContent = `${signals.length} signals`;
            }
        }
        
        // Update the signal list
        const signalList = document.getElementById('signal-list');
        if (signalList) {
            let html = '';
            signals.slice(0, 5).forEach(signal => {
                let timestamp = new Date(signal.created_at || signal.timestamp || Date.now()).toLocaleTimeString();
                let strategyName = signal.metadata?.strategy_name || 'Unknown Strategy';
                
                html += `
                    <div class="signal-item">
                        <div class="signal-symbol">${signal.symbol}</div>
                        <div class="signal-decision ${signal.decision.toLowerCase()}">${signal.decision}</div>
                        <div class="signal-strategy">${strategyName}</div>
                        <div class="signal-time">${timestamp}</div>
                    </div>
                `;
            });
            
            signalList.innerHTML = html;
        }
    }
    
    // Update strategy status (enable/disable)
    function updateStrategyStatus(strategyClass, enabled) {
        console.log(`Updating strategy ${strategyClass} to ${enabled ? 'enabled' : 'disabled'}`);
        
        // Show loading indicator
        const toggleElement = document.querySelector(`#strategy-${strategyClass} .strategy-toggle`);
        if (toggleElement) {
            toggleElement.classList.add('loading');
        }
        
        fetch(`/api/strategies/${strategyClass}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled })
        })
        .then(response => response.json())
        .then(data => {
            // Remove loading indicator
            if (toggleElement) {
                toggleElement.classList.remove('loading');
            }
            
            if (data.success) {
                // Update local strategies data
                strategies = strategies.map(s => {
                    if (s.class === strategyClass) {
                        s.enabled = enabled;
                    }
                    return s;
                });
                
                updateStrategiesUI();
                
                // Special indicator for container mode
                let usingRedis = data.note && data.note.toLowerCase().includes('redis');
                let message = `Strategy ${strategyClass} ${enabled ? 'enabled' : 'disabled'}`;
                
                if (usingRedis) {
                    message += ` <span class="badge badge-info">via Redis</span>`;
                }
                
                if (data.note) {
                    message += ` <small>(${data.note})</small>`;
                }
                
                showNotification(message);
            } else {
                console.error('Error updating strategy:', data.error);
                showNotification(`Error updating strategy: ${data.error}`, 'error');
                
                // Revert UI change
                fetchStrategies();
            }
        })
        .catch(error => {
            // Remove loading indicator
            if (toggleElement) {
                toggleElement.classList.remove('loading');
            }
            
            console.error('Error updating strategy:', error);
            showNotification('Network error updating strategy', 'error');
            
            // Revert UI change
            fetchStrategies();
        });
    }
    
    // Start strategy manager
    function startStrategyManager() {
        // Show loading indicator
        if (startStrategiesBtn) {
            startStrategiesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
            startStrategiesBtn.disabled = true;
        }
        
        fetch('/api/start_strategy_manager', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ interval: 60 }) // 60 second polling interval
        })
        .then(response => response.json())
        .then(data => {
            // Reset button
            if (startStrategiesBtn) {
                startStrategiesBtn.innerHTML = '<i class="fas fa-play"></i> Start Strategy Manager';
                startStrategiesBtn.disabled = false;
            }
            
            if (data.success) {
                strategyManagerRunning = true;
                updateManagerButtons();
                
                // Create notification with Redis badge if applicable
                let usingRedis = data.note && data.note.toLowerCase().includes('redis');
                let message = data.message || 'Strategy manager started';
                
                if (usingRedis) {
                    message += ` <span class="badge badge-info">via Redis</span>`;
                }
                
                if (data.note && !usingRedis) {
                    message += ` <small>(${data.note})</small>`;
                }
                
                showNotification(message);
                
                // Re-check health after a delay to confirm
                setTimeout(checkStrategyManagerHealth, 2000);
            } else {
                console.error('Error starting strategy manager:', data.error);
                showNotification(`Error starting strategy manager: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            // Reset button
            if (startStrategiesBtn) {
                startStrategiesBtn.innerHTML = '<i class="fas fa-play"></i> Start Strategy Manager';
                startStrategiesBtn.disabled = false;
            }
            
            console.error('Error starting strategy manager:', error);
            showNotification('Network error starting strategy manager', 'error');
        });
    }
    
    // Stop strategy manager
    function stopStrategyManager() {
        // Show loading indicator
        if (stopStrategiesBtn) {
            stopStrategiesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
            stopStrategiesBtn.disabled = true;
        }
        
        fetch('/api/stop_strategy_manager', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            // Reset button
            if (stopStrategiesBtn) {
                stopStrategiesBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Strategy Manager';
                stopStrategiesBtn.disabled = false;
            }
            
            if (data.success) {
                strategyManagerRunning = false;
                updateManagerButtons();
                
                // Create notification with Redis badge if applicable
                let usingRedis = data.note && data.note.toLowerCase().includes('redis');
                let message = data.message || 'Strategy manager stopped';
                
                if (usingRedis) {
                    message += ` <span class="badge badge-info">via Redis</span>`;
                }
                
                if (data.note && !usingRedis) {
                    message += ` <small>(${data.note})</small>`;
                }
                
                showNotification(message);
                
                // Re-check health after a delay to confirm
                setTimeout(checkStrategyManagerHealth, 2000);
            } else {
                console.error('Error stopping strategy manager:', data.error);
                showNotification(`Error stopping strategy manager: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            // Reset button
            if (stopStrategiesBtn) {
                stopStrategiesBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Strategy Manager';
                stopStrategiesBtn.disabled = false;
            }
            
            console.error('Error stopping strategy manager:', error);
            showNotification('Network error stopping strategy manager', 'error');
        });
    }
    
    // Restart strategy manager
    function restartStrategyManager() {
        // Confirm with the user
        if (!confirm("Are you sure you want to restart the strategy manager? This will stop and restart all active strategies.")) {
            return;
        }
        
        // Show loading indicator
        if (restartStrategiesBtn) {
            restartStrategiesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restarting...';
            restartStrategiesBtn.disabled = true;
        }
        
        if (strategiesStatusText) {
            strategiesStatusText.innerHTML = '<i class="fas fa-sync fa-spin" style="color: var(--warning);"></i> Restarting strategy manager...';
        }
        
        isRestarting = true;
        
        fetch('/api/restart_strategy_manager', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ interval: 60 }) // 60 second polling interval
        })
        .then(response => response.json())
        .then(data => {
            // Reset button
            if (restartStrategiesBtn) {
                restartStrategiesBtn.innerHTML = '<i class="fas fa-sync"></i> Restart Strategy Manager';
                restartStrategiesBtn.disabled = false;
            }
            
            isRestarting = false;
            
            if (data.success) {
                // Update status based on confirmation status
                let statusIcon = 'fas fa-question-circle';
                let statusColor = 'var(--warning)';
                let statusText = 'Restart status unknown';
                
                switch(data.confirmation_status) {
                    case 'confirmed':
                        statusIcon = 'fas fa-check-circle';
                        statusColor = 'var(--success)';
                        statusText = 'Strategy manager restarted successfully';
                        strategyManagerRunning = true;
                        break;
                    case 'pending':
                        statusIcon = 'fas fa-clock';
                        statusColor = 'var(--warning)';
                        statusText = 'Restart initiated, waiting for confirmation';
                        strategyManagerRunning = true;
                        break;
                    case 'uncertain':
                        statusIcon = 'fas fa-question-circle';
                        statusColor = 'var(--warning)';
                        statusText = 'Restart state uncertain';
                        strategyManagerRunning = true;
                        break;
                    case 'failed':
                        statusIcon = 'fas fa-times-circle';
                        statusColor = 'var(--danger)';
                        statusText = 'Restart failed';
                        strategyManagerRunning = false;
                        break;
                }
                
                if (strategiesStatusText) {
                    strategiesStatusText.innerHTML = `<i class="${statusIcon}" style="color: ${statusColor};"></i> ${statusText}`;
                    
                    // Add confirmation note if available
                    if (data.confirmation_note) {
                        strategiesStatusText.innerHTML += ` <small>(${data.confirmation_note})</small>`;
                    }
                }
                
                updateManagerButtons();
                
                // Create notification with Redis badge if applicable
                let usingRedis = data.restart_method === 'redis';
                let message = data.message || 'Strategy manager restarted';
                
                if (usingRedis) {
                    message += ` <span class="badge badge-info">via Redis</span>`;
                }
                
                // Add confirmation status to the message
                let statusBadgeClass = 'badge-info';
                switch(data.confirmation_status) {
                    case 'confirmed': statusBadgeClass = 'badge-success'; break;
                    case 'pending': statusBadgeClass = 'badge-warning'; break;
                    case 'uncertain': statusBadgeClass = 'badge-warning'; break;
                    case 'failed': statusBadgeClass = 'badge-danger'; break;
                }
                
                message += ` <span class="badge ${statusBadgeClass}">${data.confirmation_status}</span>`;
                
                showNotification(message);
                
                // Re-check health after a delay to confirm
                setTimeout(checkStrategyManagerHealth, 2000);
                setTimeout(checkStrategyManagerHealth, 5000);
                setTimeout(checkStrategyManagerHealth, 10000);
            } else {
                if (strategiesStatusText) {
                    strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> Restart failed`;
                }
                
                console.error('Error restarting strategy manager:', data.error);
                showNotification(`Error restarting strategy manager: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            // Reset button
            if (restartStrategiesBtn) {
                restartStrategiesBtn.innerHTML = '<i class="fas fa-sync"></i> Restart Strategy Manager';
                restartStrategiesBtn.disabled = false;
            }
            
            isRestarting = false;
            
            if (strategiesStatusText) {
                strategiesStatusText.innerHTML = `<i class="fas fa-exclamation-circle" style="color: var(--danger);"></i> Restart failed`;
            }
            
            console.error('Error restarting strategy manager:', error);
            showNotification('Network error restarting strategy manager', 'error');
        });
    }
    
    // Update manager buttons based on status
    function updateManagerButtons() {
        if (strategyManagerRunning) {
            startStrategiesBtn.style.display = 'none';
            stopStrategiesBtn.style.display = 'inline-block';
            restartStrategiesBtn.style.display = 'inline-block';
            strategiesStatusText.innerHTML = '<i class="fas fa-play-circle" style="color: var(--success);"></i> Strategy manager running';
        } else {
            startStrategiesBtn.style.display = 'inline-block';
            stopStrategiesBtn.style.display = 'none';
            restartStrategiesBtn.style.display = 'none';
            strategiesStatusText.innerHTML = '<i class="fas fa-stop-circle" style="color: var(--warning);"></i> Strategy manager stopped';
        }
    }
    
    // Show notification - use the global function if available
    function showNotification(message, type = 'success') {
        // Use the toast function from the main dashboard if it exists
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }
        
        // Fallback: Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Show and then fade out
        setTimeout(() => {
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(toast);
                }, 300);
            }, 3000);
        }, 100);
    }
    
    // Reset strategy manager (emergency function)
    function resetStrategyManager() {
        if (!confirm("⚠️ EMERGENCY RESET ⚠️\n\nThis will force reset the strategy manager state in Redis. This is only for recovery when the strategy manager is stuck or in an inconsistent state.\n\nContinue?")) {
            return;
        }
        
        fetch('/api/reset_strategy_manager', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Show the restart command if provided
                let message = data.message;
                
                if (data.restart_command) {
                    message += `\n\nYou may need to run this command to restart the backend service:\n${data.restart_command}`;
                }
                
                showNotification('Strategy manager state reset in Redis', 'warning');
                
                // Show more detailed alert
                alert(`${message}\n\nPlease manually refresh the page after a few seconds.\n\nFound strategies: ${data.found_strategies.join(', ') || 'None'}\nSignal count: ${data.signal_count}`);
                
                // Immediately check the health again
                setTimeout(checkStrategyManagerHealth, 1000);
            } else {
                console.error('Error resetting strategy manager:', data.message);
                showNotification(`Error resetting strategy manager: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('Network error resetting strategy manager:', error);
            showNotification('Network error resetting strategy manager', 'error');
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeStrategies);
    } else {
        initializeStrategies();
    }
})(); 