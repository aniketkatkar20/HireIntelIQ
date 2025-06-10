      // Voice Detection JavaScript Integration
        class VoiceDetectionInterface {
            constructor() {
                this.isRegistered = false;
                this.isMonitoring = false;
                this.registrationInProgress = false;
                this.statusCheckInterval = null;
                
                this.initializeEventListeners();
                this.checkAudioAvailability();
                this.startStatusPolling();
            }

            initializeEventListeners() {
                // Audio check
                document.getElementById('checkAudioBtn').addEventListener('click', () => {
                    this.checkAudioAvailability();
                });

                // Voice registration
                document.getElementById('registerVoiceBtn').addEventListener('click', () => {
                    this.registerVoice(10);
                });

                document.getElementById('testVoiceBtn').addEventListener('click', () => {
                    this.testVoiceRegistration(5);
                });

                // Profile management
                document.getElementById('loadProfilesBtn').addEventListener('click', () => {
                    this.loadVoiceProfiles();
                });

                document.getElementById('profileSelect').addEventListener('change', (e) => {
                    if (e.target.value) {
                        this.loadVoiceProfile(e.target.value);
                    }
                });

                // Monitoring control
                document.getElementById('startMonitoringBtn').addEventListener('click', () => {
                    this.startMonitoring();
                });

                document.getElementById('stopMonitoringBtn').addEventListener('click', () => {
                    this.stopMonitoring();
                });
            }

            async checkAudioAvailability() {
                try {
                    this.showProgress(true, 'Checking audio device...');
                    
                    const response = await fetch('/check-audio-availability');
                    const data = await response.json();
                    
                    const statusElement = document.getElementById('audioStatusValue');
                    
                    if (data.available) {
                        statusElement.textContent = 'Available ✓';
                        statusElement.style.color = '#28a745';
                        this.showAlert('Audio device detected successfully', 'success');
                    } else {
                        statusElement.textContent = 'Not Available ✗';
                        statusElement.style.color = '#dc3545';
                        this.showAlert('No audio device detected. Please check your microphone.', 'error');
                    }
                } catch (error) {
                    console.error('Audio check failed:', error);
                    this.showAlert('Failed to check audio device', 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async registerVoice(duration) {
                if (this.registrationInProgress) return;
                
                try {
                    this.registrationInProgress = true;
                    this.showRecordingIndicator(true, `Recording for ${duration} seconds...`);
                    this.showProgress(true, 'Starting voice registration...');
                    
                    // Start registration
                    const response = await fetch('/start-voice-registration', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ duration })
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        // Show countdown
                        this.showCountdown(duration);
                        
                        // Poll for completion
                        this.pollRegistrationStatus();
                    } else {
                        throw new Error(data.message);
                    }
                } catch (error) {
                    console.error('Registration failed:', error);
                    this.showAlert(`Registration failed: ${error.message}`, 'error');
                    this.registrationInProgress = false;
                    this.showRecordingIndicator(false);
                    this.showProgress(false);
                }
            }

            async testVoiceRegistration(duration) {
                try {
                    this.showProgress(true, 'Testing voice registration...');
                    
                    const response = await fetch('/test-voice-registration', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ duration })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showAlert('Voice registration test successful!', 'success');
                        this.updateRegistrationStatus(true);
                    } else {
                        this.showAlert('Voice registration test failed', 'error');
                    }
                } catch (error) {
                    console.error('Test failed:', error);
                    this.showAlert('Test failed: ' + error.message, 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async loadVoiceProfiles() {
                try {
                    this.showProgress(true, 'Loading voice profiles...');
                    
                    const response = await fetch('/get-voice-profiles');
                    const data = await response.json();
                    
                    const select = document.getElementById('profileSelect');
                    select.innerHTML = '<option value="">Select a profile...</option>';
                    
                    data.profiles.forEach(profile => {
                        const option = document.createElement('option');
                        option.value = profile.session_id;
                        option.textContent = `${profile.session_id} (${new Date(profile.timestamp).toLocaleDateString()})`;
                        select.appendChild(option);
                    });
                    
                    this.showAlert(`Loaded ${data.profiles.length} voice profiles`, 'success');
                } catch (error) {
                    console.error('Failed to load profiles:', error);
                    this.showAlert('Failed to load voice profiles', 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async loadVoiceProfile(sessionId) {
                try {
                    this.showProgress(true, 'Loading voice profile...');
                    
                    const response = await fetch('/load-voice-profile', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: sessionId })
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        this.updateRegistrationStatus(true);
                        this.showAlert(`Voice profile loaded: ${sessionId}`, 'success');
                    } else {
                        throw new Error(data.message);
                    }
                } catch (error) {
                    console.error('Failed to load profile:', error);
                    this.showAlert('Failed to load voice profile', 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async startMonitoring() {
                try {
                    this.showProgress(true, 'Starting voice monitoring...');
                    
                    const response = await fetch('/start-audio-monitoring', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        this.isMonitoring = true;
                        this.updateMonitoringUI();
                        this.showAlert('Voice monitoring started', 'success');
                        
                        // Start interview monitoring
                        await fetch('/start-interview-monitoring', { method: 'POST' });
                    } else {
                        throw new Error(data.message);
                    }
                } catch (error) {
                    console.error('Failed to start monitoring:', error);
                    this.showAlert('Failed to start monitoring: ' + error.message, 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async stopMonitoring() {
                try {
                    await fetch('/stop-audio-monitoring', { method: 'POST' });
                    await fetch('/end-interview-monitoring', { method: 'POST' });
                    
                    this.isMonitoring = false;
                    this.updateMonitoringUI();
                    this.showAlert('Voice monitoring stopped', 'success');
                } catch (error) {
                    console.error('Failed to stop monitoring:', error);
                    this.showAlert('Failed to stop monitoring', 'error');
                }
            }

            showCountdown(duration) {
                let remaining = duration;
                const interval = setInterval(() => {
                    this.showProgress(true, `Recording... ${remaining}s remaining`, ((duration - remaining) / duration) * 100);
                    remaining--;
                    
                    if (remaining < 0) {
                        clearInterval(interval);
                        this.showProgress(true, 'Processing voice data...', 100);
                    }
                }, 1000);
            }

            async pollRegistrationStatus() {
                const pollInterval = setInterval(async () => {
                    try {
                        const response = await fetch('/check-registration-status');
                        const data = await response.json();
                        
                        if (data.registration.status === 'completed') {
                            clearInterval(pollInterval);
                            this.registrationInProgress = false;
                            this.showRecordingIndicator(false);
                            this.showProgress(false);
                            
                            if (data.registration.success) {
                                this.updateRegistrationStatus(true);
                                this.showAlert('Voice registered successfully!', 'success');
                            } else {
                                this.showAlert('Voice registration failed', 'error');
                            }
                        } else if (data.registration.status === 'failed' || data.registration.status === 'error') {
                            clearInterval(pollInterval);
                            this.registrationInProgress = false;
                            this.showRecordingIndicator(false);
                            this.showProgress(false);
                            this.showAlert(`Registration failed: ${data.registration.error}`, 'error');
                        }
                    } catch (error) {
                        console.error('Status poll failed:', error);
                    }
                }, 1000);
            }

            startStatusPolling() {
                this.statusCheckInterval = setInterval(async () => {
                    await this.updateVoiceWarnings();
                    await this.checkInterviewStatus();
                }, 2000);
            }

            async updateVoiceWarnings() {
                try {
                    const response = await fetch('/get-voice-warnings');
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        document.getElementById('warningCount').textContent = `${data.warnings}/${data.max_warnings}`;
                        document.getElementById('malpracticeCount').textContent = `${data.malpractice_count}/${data.max_malpractice}`;
                        
                        // Update colors based on warning level
                        const warningElement = document.getElementById('warningCount');
                        if (data.warnings >= data.max_warnings) {
                            warningElement.style.color = '#dc3545';
                        } else if (data.warnings > 0) {
                            warningElement.style.color = '#ffc107';
                        } else {
                            warningElement.style.color = '#28a745';
                        }
                    }
                } catch (error) {
                    console.error('Failed to update warnings:', error);
                }
            }

            async checkInterviewStatus() {
                try {
                    const response = await fetch('/check-interview-status');
                    const data = await response.json();
                    
                    if (data.interview_status.status === 'cancelled') {
                        document.getElementById('interviewStatus').textContent = 'Cancelled';
                        document.getElementById('interviewStatus').style.color = '#dc3545';
                        this.showAlert(`Interview cancelled: ${data.interview_status.reason}`, 'error');
                    }
                } catch (error) {
                    console.error('Failed to check interview status:', error);
                }
            }

            updateRegistrationStatus(registered) {
                this.isRegistered = registered;
                const statusElement = document.getElementById('registrationStatus');
                const startBtn = document.getElementById('startMonitoringBtn');
                
                if (registered) {
                    statusElement.textContent = 'Registered ✓';
                    statusElement.style.color = '#28a745';
                    startBtn.disabled = false;
                    startBtn.classList.remove('btn-disabled');
                } else {
                    statusElement.textContent = 'Not Registered';
                    statusElement.style.color = '#dc3545';
                    startBtn.disabled = true;
                    startBtn.classList.add('btn-disabled');
                }
            }

            updateMonitoringUI() {
                const startBtn = document.getElementById('startMonitoringBtn');
                const stopBtn = document.getElementById('stopMonitoringBtn');
                const statusElement = document.getElementById('monitoringStatus');
                
                if (this.isMonitoring) {
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'block';
                    statusElement.textContent = 'Active ✓';
                    statusElement.style.color = '#28a745';
                } else {
                    startBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                    statusElement.textContent = 'Inactive';
                    statusElement.style.color = '#6c757d';
                }
            }

            showRecordingIndicator(show, text = 'Recording...') {
                const indicator = document.getElementById('recordingIndicator');
                const textElement = document.getElementById('recordingText');
                
                if (show) {
                    indicator.classList.add('active');
                    textElement.textContent = text;
                } else {
                    indicator.classList.remove('active');
                }
            }
            
showProgress(show, text = '', percentage = 0) {
                const container = document.getElementById('progressContainer');
                const fill = document.getElementById('progressFill');
                const textElement = document.getElementById('progressText');
                
                if (show) {
                    container.style.display = 'block';
                    fill.style.width = percentage + '%';
                    textElement.textContent = text;
                } else {
                    container.style.display = 'none';
                    fill.style.width = '0%';
                    textElement.textContent = '';
                }
            }
            showAlert(message, type = 'info') {
                const alertContainer = document.getElementById('alertContainer');
                const warningSystem = document.getElementById('warningSystem');
                
                // Show the warning system if it's hidden
                warningSystem.style.display = 'block';
                
                // Create alert element
                const alertElement = document.createElement('div');
                alertElement.className = `warning-item ${type}`;
                
                // Create icon based on type
                let iconSVG = '';
                let title = '';
                
                switch (type) {
                    case 'success':
                        title = 'Success';
                        iconSVG = `<svg class="warning-icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                        </svg>`;
                        break;
                    case 'error':
                        title = 'Error';
                        iconSVG = `<svg class="warning-icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/>
                        </svg>`;
                        break;
                    default:
                        title = 'Info';
                        iconSVG = `<svg class="warning-icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
                        </svg>`;
                }
                
                alertElement.innerHTML = `
                    ${iconSVG}
                    <div class="warning-content">
                        <div class="warning-title">${title}</div>
                        <div class="warning-message">${message}</div>
                    </div>
                `;
                
                // Add to container
                alertContainer.appendChild(alertElement);
                
                // Auto-remove after 5 seconds
                setTimeout(() => {
                    if (alertElement.parentNode) {
                        alertElement.remove();
                        
                        // Hide warning system if no alerts remain
                        if (alertContainer.children.length === 0) {
                            warningSystem.style.display = 'none';
                        }
                    }
                }, 5000);
            }

            // Cleanup method
            destroy() {
                if (this.statusCheckInterval) {
                    clearInterval(this.statusCheckInterval);
                }
                
                // Stop monitoring if active
                if (this.isMonitoring) {
                    this.stopMonitoring();
                }
            }

            // Additional utility methods
            async getSystemStatus() {
                try {
                    const response = await fetch('/get-system-status');
                    const data = await response.json();
                    return data;
                } catch (error) {
                    console.error('Failed to get system status:', error);
                    return null;
                }
            }

            async exportVoiceData() {
                try {
                    this.showProgress(true, 'Exporting voice data...');
                    
                    const response = await fetch('/export-voice-data');
                    const blob = await response.blob();
                    
                    // Create download link
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `voice_data_${new Date().toISOString().split('T')[0]}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    this.showAlert('Voice data exported successfully', 'success');
                } catch (error) {
                    console.error('Export failed:', error);
                    this.showAlert('Failed to export voice data', 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            async resetVoiceSystem() {
                try {
                    this.showProgress(true, 'Resetting voice system...');
                    
                    const response = await fetch('/reset-voice-system', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        // Reset UI state
                        this.isRegistered = false;
                        this.isMonitoring = false;
                        this.updateRegistrationStatus(false);
                        this.updateMonitoringUI();
                        
                        // Clear alerts
                        document.getElementById('alertContainer').innerHTML = '';
                        document.getElementById('warningSystem').style.display = 'none';
                        
                        // Reset counters
                        document.getElementById('warningCount').textContent = '0/3';
                        document.getElementById('malpracticeCount').textContent = '0/5';
                        document.getElementById('interviewStatus').textContent = 'Ready';
                        
                        this.showAlert('Voice system reset successfully', 'success');
                    } else {
                        throw new Error(data.message);
                    }
                } catch (error) {
                    console.error('Reset failed:', error);
                    this.showAlert('Failed to reset voice system', 'error');
                } finally {
                    this.showProgress(false);
                }
            }

            // Enhanced error handling
            handleError(error, context = '') {
                console.error(`Voice Detection Error ${context}:`, error);
                
                let message = 'An unexpected error occurred';
                
                if (error.name === 'NetworkError' || error.message.includes('fetch')) {
                    message = 'Network connection error. Please check your internet connection.';
                } else if (error.name === 'NotAllowedError') {
                    message = 'Microphone access denied. Please allow microphone permissions.';
                } else if (error.name === 'TimeoutError') {
                    message = 'Request timed out. Please try again.';
                } else if (error.message) {
                    message = error.message;
                }
                
                this.showAlert(`${context} ${message}`, 'error');
            }

            // Voice quality check
            async checkVoiceQuality() {
                try {
                    this.showProgress(true, 'Checking voice quality...');
                    
                    const response = await fetch('/check-voice-quality');
                    const data = await response.json();
                    
                    if (data.quality_score >= 0.8) {
                        this.showAlert(`Voice quality: Excellent (${Math.round(data.quality_score * 100)}%)`, 'success');
                    } else if (data.quality_score >= 0.6) {
                        this.showAlert(`Voice quality: Good (${Math.round(data.quality_score * 100)}%)`, 'info');
                    } else {
                        this.showAlert(`Voice quality: Poor (${Math.round(data.quality_score * 100)}%). Consider adjusting your microphone.`, 'error');
                    }
                } catch (error) {
                    this.handleError(error, 'Voice quality check failed:');
                } finally {
                    this.showProgress(false);
                }
            }
        }

        // Initialize the voice detection interface when DOM is loaded
        document.addEventListener('DOMContentLoaded', function() {
            try {
                window.voiceInterface = new VoiceDetectionInterface();
                console.log('Voice Detection Interface initialized successfully');
            } catch (error) {
                console.error('Failed to initialize Voice Detection Interface:', error);
                
                // Show error message to user
                const errorDiv = document.createElement('div');
                errorDiv.className = 'warning-item error';
                errorDiv.innerHTML = `
                    <svg class="warning-icon" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/>
                    </svg>
                    <div class="warning-content">
                        <div class="warning-title">Initialization Error</div>
                        <div class="warning-message">Failed to initialize voice detection system. Please refresh the page.</div>
                    </div>
                `;
                
                const voiceSection = document.getElementById('voiceSection');
                if (voiceSection) {
                    voiceSection.insertBefore(errorDiv, voiceSection.firstChild);
                }
            }
        });

        // Handle page unload
        window.addEventListener('beforeunload', function() {
            if (window.voiceInterface) {
                window.voiceInterface.destroy();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(event) {
            if (!window.voiceInterface) return;
            
            // Alt + R for registration
            if (event.altKey && event.key === 'r') {
                event.preventDefault();
                document.getElementById('registerVoiceBtn').click();
            }
            
            // Alt + M for monitoring toggle
            if (event.altKey && event.key === 'm') {
                event.preventDefault();
                if (window.voiceInterface.isMonitoring) {
                    document.getElementById('stopMonitoringBtn').click();
                } else {
                    document.getElementById('startMonitoringBtn').click();
                }
            }
            
            // Alt + T for test
            if (event.altKey && event.key === 't') {
                event.preventDefault();
                document.getElementById('testVoiceBtn').click();
            }
        });

        // Periodic health check
        setInterval(async function() {
            if (window.voiceInterface) {
                try {
                    const status = await window.voiceInterface.getSystemStatus();
                    if (status && status.status === 'error') {
                        window.voiceInterface.showAlert('System health check failed', 'error');
                    }
                } catch (error) {
                    console.error('Health check failed:', error);
                }
            }
        }, 30000); // Every 30 seconds


  document.getElementById('resultForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = {
      name: document.getElementById('name').value,
      score: document.getElementById('score').value,
    };

    const response = await fetch('/submit-result', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    });

    const result = await response.json();

    const msgDiv = document.getElementById('statusMsg');
    msgDiv.textContent = result.message;

    if (result.status === 'success') {
      msgDiv.style.color = 'green';
    } else {
      msgDiv.style.color = 'red';
    }
  });