
  // Voice Interview System JavaScript
// Enhanced Voice Interview System JavaScript
class VoiceInterviewSystem {
    constructor() {
        this.recognition = null;
        this.synthesis = null;
        this.speechSynthesisUtterance = null;
        this.isListening = false;
        this.isInterviewActive = false;
        this.currentQuestionIndex = 0;
        this.questions = [];
        this.qaPairs = [];
        this.currentTranscript = '';
        this.candidateInfo = {};
        this.results = [];
        this.timer = null;
        
        this.initializeSpeechAPI();
        this.bindEvents();
        this.loadResults();
    }

    initializeSpeechAPI() {
        // Check speech synthesis support
        if (!('speechSynthesis' in window)) {
            this.showStatus('error', 'Speech synthesis is not supported in your browser. Please use Chrome, Firefox, or Safari.');
            return;
        }
        
        // Check speech recognition support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.showStatus('error', 'Speech recognition is not supported in your browser. Please use Chrome or Safari.');
            return;
        }

        // Initialize Speech Recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        this.recognition.maxAlternatives = 1;

        // Initialize Speech Synthesis
        this.synthesis = window.speechSynthesis;

        this.showStatus('success', '🚀 Voice interview system ready and optimized!');
    }

    bindEvents() {
        // Wait for page to load
        document.addEventListener('DOMContentLoaded', () => {
            console.log('Page loaded, setting up event listeners...');
        });

        // File input events
        const resumeInput = document.getElementById('resume');
        const jdInput = document.getElementById('jd');
        
        if (resumeInput) resumeInput.addEventListener('change', this.handleFileSelect.bind(this));
        if (jdInput) jdInput.addEventListener('change', this.handleFileSelect.bind(this));
        
        // Button events
        const startInterviewBtn = document.getElementById('startInterview');
        const startVoiceBtn = document.getElementById('startInterviewVoice');
        const stopBtn = document.getElementById('stopButton');
        const newInterviewBtn = document.getElementById('startNewInterview');
        const sortSelect = document.getElementById('sortBy');
        
        if (startInterviewBtn) startInterviewBtn.addEventListener('click', this.generateQuestions.bind(this));
        if (startVoiceBtn) startVoiceBtn.addEventListener('click', this.startVoiceInterview.bind(this));
        if (stopBtn) stopBtn.addEventListener('click', this.stopCurrentAnswer.bind(this));
        if (newInterviewBtn) newInterviewBtn.addEventListener('click', this.startNewInterview.bind(this));
        if (sortSelect) sortSelect.addEventListener('change', this.sortResults.bind(this));
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        const container = event.target.closest('.file-input-container');
        const label = container?.querySelector('.file-label');
        
        if (file && label) {
            label.innerHTML = `<strong>✅ ${file.name}</strong><br><small>File selected successfully</small>`;
            if (container) {
                container.style.borderColor = 'rgba(129, 251, 184, 0.4)';
                container.style.background = 'rgba(129, 251, 184, 0.1)';
            }
        }
    }

    async generateQuestions() {
        const candidateNameEl = document.getElementById('candidateName');
        const candidateEmailEl = document.getElementById('candidateEmail');
        const candidatePositionEl = document.getElementById('candidatePosition');
        const resumeFile = document.getElementById('resume')?.files[0];
        const jdFile = document.getElementById('jd')?.files[0];

        const candidateName = candidateNameEl?.value.trim() || '';
        const candidateEmail = candidateEmailEl?.value.trim() || '';
        const candidatePosition = candidatePositionEl?.value.trim() || '';

        if (!candidateName && candidateNameEl) {
            this.showStatus('error', 'Please enter candidate name');
            return;
        }

        if (!resumeFile || !jdFile) {
            this.showStatus('error', '⚠️ Please upload both files to continue.');
            return;
        }

        this.candidateInfo = {
            name: candidateName,
            email: candidateEmail,
            position: candidatePosition
        };

        this.showStatus('success', '🔄 Uploading files and generating intelligent questions...');
        const startBtn = document.getElementById('startInterview');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.classList.add('pulse');
        }

        const formData = new FormData();
        formData.append('resume', resumeFile);
        formData.append('jd', jdFile);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            console.log('Upload response:', result);

            if (result.status === 'success') {
                this.questions = result.result?.questions || [];
                console.log('Questions loaded:', this.questions.length, 'questions');
                
                if (this.questions.length === 0) {
                    this.showStatus('error', '❌ No questions were generated. Please check your files and try again.');
                    if (startBtn) {
                        startBtn.disabled = false;
                        startBtn.classList.remove('pulse');
                    }
                    return;
                }
                
                this.showAudioControls();
                this.showStatus('success', `✅ Perfect! ${this.questions.length} intelligent questions generated. Ready for your voice interview.`);
                if (startBtn) startBtn.classList.remove('pulse');
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showStatus('error', `❌ Upload failed: ${error.message}`);
        } finally {
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.classList.remove('pulse');
            }
        }
    }

    showAudioControls() {
        const audioControls = document.getElementById('audioControls');
        if (audioControls) {
            audioControls.classList.remove('hidden');
            
            const currentNameEl = document.getElementById('currentName');
            const currentEmailEl = document.getElementById('currentEmail');
            const currentPositionEl = document.getElementById('currentPosition');
            
            if (currentNameEl) currentNameEl.textContent = this.candidateInfo.name;
            if (currentEmailEl) currentEmailEl.textContent = this.candidateInfo.email || 'Not provided';
            if (currentPositionEl) currentPositionEl.textContent = this.candidateInfo.position || 'Not specified';
            
            // Scroll to audio controls
            audioControls.scrollIntoView({ behavior: 'smooth' });
        }
    }

    async startVoiceInterview() {
        console.log('Start Voice Interview clicked');
        
        if (this.isInterviewActive) {
            this.showStatus('error', '⚠️ Interview is already in progress.');
            return;
        }
        
        if (this.questions.length === 0) {
            this.showStatus('error', '⚠️ No questions available. Please upload files first.');
            return;
        }
        
        this.isInterviewActive = true;
        this.currentQuestionIndex = 0;
        this.qaPairs = [];
        
        // Show interview is starting
        const currentQuestionEl = document.getElementById('currentQuestion');
        const transcriptEl = document.getElementById('transcript');
        const answerEl = document.getElementById('answer');
        
        if (currentQuestionEl) currentQuestionEl.innerHTML = '🚀 <span class="pulse">Starting your interview...</span>';
        if (transcriptEl) transcriptEl.textContent = '';
        if (answerEl) answerEl.textContent = '';
        
        const startVoiceBtn = document.getElementById('startInterviewVoice');
        if (startVoiceBtn) startVoiceBtn.disabled = true;
        
        console.log('Starting voice interview with', this.questions.length, 'questions');
        this.runVoiceInterview();
    }

    runVoiceInterview() {
        if (this.currentQuestionIndex >= this.questions.length) {
            console.log('Interview completed');
            this.isInterviewActive = false;
            const startVoiceBtn = document.getElementById('startInterviewVoice');
            if (startVoiceBtn) startVoiceBtn.disabled = false;
            
            this.speak("🎉 Interview completed successfully! Thank you for your time. Now calculating your scores...", () => {
                setTimeout(() => this.submitTranscriptForScoring(), 2000);
            });
            return;
        }

        const question = this.questions[this.currentQuestionIndex];
        console.log(`Question ${this.currentQuestionIndex + 1}/${this.questions.length}: ${question}`);
        
        const currentQuestionEl = document.getElementById('currentQuestion');
        const transcriptEl = document.getElementById('transcript');
        const answerEl = document.getElementById('answer');
        
        if (currentQuestionEl) {
            currentQuestionEl.innerHTML = `
                <strong>Question ${this.currentQuestionIndex + 1} of ${this.questions.length}:</strong><br><br>
                ${question}
            `;
        }
        if (transcriptEl) transcriptEl.innerHTML = '🎯 <span class="pulse">Preparing to ask question...</span>';
        if (answerEl) answerEl.textContent = '';

        // Add a delay to ensure UI updates before speaking
        setTimeout(() => {
            this.speak(question, () => {
                console.log('Question spoken, starting to listen...');
                setTimeout(() => this.startListening(question), 1000);
            });
        }, 1000);
    }

    speak(text, callback) {
        console.log('Speaking:', text.substring(0, 50) + '...');
        
        // Cancel any ongoing speech
        if (this.synthesis) {
            this.synthesis.cancel();
        }
        
        // Wait for cancellation to complete
        setTimeout(() => {
            if (!text || text.trim() === '') {
                console.error('Empty text to speak');
                if (callback) callback();
                return;
            }
            
            this.speechSynthesisUtterance = new SpeechSynthesisUtterance(text);
            this.speechSynthesisUtterance.lang = 'en-US';
            this.speechSynthesisUtterance.rate = 0.8;
            this.speechSynthesisUtterance.pitch = 1.0;
            this.speechSynthesisUtterance.volume = 0.9;
            
            this.speechSynthesisUtterance.onstart = () => {
                console.log('Speech started');
            };
            
            this.speechSynthesisUtterance.onend = () => {
                console.log('Speech ended');
                if (callback) {
                    setTimeout(callback, 500);
                }
            };
            
            this.speechSynthesisUtterance.onerror = (event) => {
                console.error('Speech error:', event.error);
                if (callback) {
                    setTimeout(callback, 500);
                }
            };
            
            try {
                if (this.synthesis) {
                    this.synthesis.speak(this.speechSynthesisUtterance);
                }
            } catch (error) {
                console.error('Speech synthesis error:', error);
                if (callback) callback();
            }
        }, 200);
    }

    startListening(question) {
        console.log('Starting speech recognition for question:', question.substring(0, 30) + '...');
        
        if (!this.recognition) {
            this.showStatus('error', 'Speech recognition not supported');
            return;
        }

        try {
            let finalTranscript = "";
            this.isListening = false;

            // Reset recognition handlers
            this.recognition.onstart = () => {
                console.log('Speech recognition started');
                this.isListening = true;
                const transcriptEl = document.getElementById('transcript');
                if (transcriptEl) {
                    transcriptEl.innerHTML = `
                        🎤 <span class="listening-indicator">
                            <span class="listening-dot"></span>
                            <span class="listening-dot"></span>
                            <span class="listening-dot"></span>
                        </span> 
                        Listening... Please speak your answer clearly.
                    `;
                }
            };

            this.recognition.onresult = (event) => {
                let interimTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript + ' ';
                    } else {
                        interimTranscript += transcript;
                    }
                }
                
                const displayText = (finalTranscript + interimTranscript).trim();
                const transcriptEl = document.getElementById('transcript');
                if (displayText && transcriptEl) {
                    transcriptEl.textContent = displayText;
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.isListening = false;
                clearTimeout(this.timer);
                
                let errorMessage = '❌ Speech recognition error: ';
                switch(event.error) {
                    case 'no-speech':
                        errorMessage += 'No speech detected. Please try again.';
                        break;
                    case 'audio-capture':
                        errorMessage += 'Microphone not found. Please check your microphone.';
                        break;
                    case 'not-allowed':
                        errorMessage += 'Microphone access denied. Please allow microphone access and refresh the page.';
                        break;
                    case 'network':
                        errorMessage += 'Network error. Please check your internet connection.';
                        break;
                    default:
                        errorMessage += event.error;
                }
                
                this.showStatus('error', errorMessage);
                
                // Ask if user wants to retry or skip
                if (confirm('Would you like to try again? Click Cancel to skip this question.')) {
                    setTimeout(() => this.startListening(question), 2000);
                } else {
                    // Skip this question
                    this.currentQuestionIndex++;
                    setTimeout(() => this.runVoiceInterview(), 1000);
                }
            };

            this.recognition.onend = () => {
                console.log('Speech recognition ended');
                this.isListening = false;
                clearTimeout(this.timer);

                const answer = finalTranscript.trim();
                
                if (!answer || answer.length < 3) {
                    console.log('No valid answer detected');
                    const transcriptEl = document.getElementById('transcript');
                    if (transcriptEl) transcriptEl.textContent = 'No clear answer detected.';
                    
                    if (confirm('No clear answer was detected. Would you like to try again?')) {
                        setTimeout(() => this.startListening(question), 2000);
                        return;
                    } else {
                        // Use "No response" as answer
                        finalTranscript = "No response provided";
                    }
                }

                const finalAnswer = finalTranscript.trim() || "No response provided";
                console.log('Final answer:', finalAnswer.substring(0, 50) + '...');
                
                this.qaPairs.push({ question, answer: finalAnswer });
                const answerEl = document.getElementById('answer');
                if (answerEl) answerEl.textContent = finalAnswer;

                // Save the answer
                this.saveTranscript(question, finalAnswer);

                // Move to next question
                this.currentQuestionIndex++;
                setTimeout(() => this.runVoiceInterview(), 2000);
            };

            this.recognition.start();

            // Auto stop after 2 minutes
            this.timer = setTimeout(() => {
                console.log('Auto-stopping recognition after 2 minutes');
                if (this.isListening) {
                    this.recognition.stop();
                }
            }, 60000);

        } catch (error) {
            console.error('Error starting speech recognition:', error);
            this.showStatus('error', '❌ Failed to start speech recognition: ' + error.message);
        }
    }

    stopCurrentAnswer() {
        console.log('Manual stop clicked');
        clearTimeout(this.timer);
        if (this.isListening && this.recognition) {
            this.recognition.stop();
        }
    }

    async saveTranscript(question, answer) {
        try {
            const response = await fetch('/save-transcript', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    question: question,
                    answer: answer
                })
            });

            if (!response.ok) {
                console.error('Failed to save transcript');
            }
            const data = await response.json();
            console.log('Transcript saved:', data);
        } catch (error) {
            console.error('Error saving transcript:', error);
        }
    }

    async submitTranscriptForScoring() {
        console.log('Submitting transcript for scoring...');
        
        const currentQuestionEl = document.getElementById('currentQuestion');
        const transcriptEl = document.getElementById('transcript');
        
        if (currentQuestionEl) currentQuestionEl.innerHTML = '📊 <span class="pulse">Calculating your scores...</span>';
        if (transcriptEl) transcriptEl.textContent = 'Please wait while we analyze your responses with advanced AI...';
        
        try {
            const response = await fetch('/score-transcript');
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            console.log('Scoring data received:', data);

            if (data.status !== 'success') {
                this.showStatus('error', '❌ Error fetching score: ' + data.message);
                return;
            }

            // Display results
            this.displayScores(data.scores);
        } catch (error) {
            console.error('Error fetching score:', error);
            this.showStatus('error', '❌ Error calculating scores: ' + error.message);
        }
    }

    displayScores(scores) {
        const currentQuestionEl = document.getElementById('currentQuestion');
        const transcriptEl = document.getElementById('transcript');
        const scoreListEl = document.getElementById('scoreList');
        const overallScoreEl = document.getElementById('overallScore');
        
        if (currentQuestionEl) currentQuestionEl.innerHTML = '🎯 <strong>Interview Complete - Results Ready</strong>';
        if (transcriptEl) transcriptEl.textContent = '✨ Thank you for completing the interview! Your results are displayed below.';
        
        if (scoreListEl) {
            scoreListEl.innerHTML = '';
            
            if (scores && scores.scores && Array.isArray(scores.scores)) {
                scores.scores.forEach((scoreObj, index) => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <strong>${scoreObj.progress}</strong><br>
                        <span style="font-size: 1.2em; font-weight: 600;">Score: ${scoreObj.score}%</span>
                    `;
                    li.className = 'score-item';
                    
                    // Color coding based on score
                    if (scoreObj.score >= 70) {
                        li.style.background = 'rgba(129, 251, 184, 0.15)';
                        li.style.borderColor = 'rgba(129, 251, 184, 0.3)';
                        li.style.color = '#10b981';
                    } else if (scoreObj.score >= 50) {
                        li.style.background = 'rgba(255, 211, 61, 0.15)';
                        li.style.borderColor = 'rgba(255, 211, 61, 0.3)';
                        li.style.color = '#f59e0b';
                    } else {
                        li.style.background = 'rgba(255, 107, 107, 0.15)';
                        li.style.borderColor = 'rgba(255, 107, 107, 0.3)';
                        li.style.color = '#ef4444';
                    }
                    
                    scoreListEl.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = 'No detailed scores available';
                li.className = 'score-item';
                scoreListEl.appendChild(li);
            }
        }

        if (overallScoreEl) {
            if (scores && !isNaN(scores.overall)) {
                const overall = scores.overall;
                overallScoreEl.innerHTML = `
                    <div style="margin-bottom: 8px;">Overall Performance</div>
                    <div style="font-size: 3rem;">${overall.toFixed(1)}%</div>
                    <div style="font-size: 1rem; opacity: 0.8;">
                        ${overall >= 70 ? '🎉 Excellent Performance!' : overall >= 50 ? '👍 Good Performance!' : '💪 Room for Improvement'}
                    </div>
                `;
                overallScoreEl.style.color = overall >= 70 ? '#10b981' : overall >= 50 ? '#f59e0b' : '#ef4444';
            } else {
                overallScoreEl.innerHTML = `
                    <div style="font-size: 1.5rem;">Overall score not available</div>
                `;
            }
        }
        
        // Show completion message
        setTimeout(() => {
            const finalScore = scores.overall ? scores.overall.toFixed(1) + '%' : 'not available';
            this.showStatus('success', `🎉 Interview completed successfully! Your overall score is ${finalScore}`);
        }, 1000);

        // Save to results
        if (scores && scores.overall) {
            this.saveInterviewResult(scores);
        }
    }

    saveInterviewResult(scores) {
        const result = {
            id: Date.now(),
            name: this.candidateInfo.name,
            email: this.candidateInfo.email,
            position: this.candidateInfo.position,
            score: Math.round(scores.overall),
            timestamp: new Date().toISOString(),
            qaPairs: this.qaPairs,
            detailedScores: scores.scores || []
        };

        this.results.push(result);
        this.saveResults();
    }

    startNewInterview() {
        // Reset form
        const candidateNameEl = document.getElementById('candidateName');
        const candidateEmailEl = document.getElementById('candidateEmail');
        const candidatePositionEl = document.getElementById('candidatePosition');
        const resumeEl = document.getElementById('resume');
        const jdEl = document.getElementById('jd');
        
        if (candidateNameEl) candidateNameEl.value = '';
        if (candidateEmailEl) candidateEmailEl.value = '';
        if (candidatePositionEl) candidatePositionEl.value = '';
        if (resumeEl) resumeEl.value = '';
        if (jdEl) jdEl.value = '';
        
        // Reset file input displays
        document.querySelectorAll('.file-input-container').forEach(container => {
            const label = container.querySelector('.file-label');
            const input = container.querySelector('input');
            if (label && input) {
                const isResume = input.id === 'resume';
                label.innerHTML = isResume ? 
                    '<strong>Upload Resume</strong><br><small>PDF, DOCX, or TXT format</small>' :
                    '<strong>Upload Job Description</strong><br><small>PDF, DOCX, or TXT format</small>';
                container.style.borderColor = 'var(--glass-border)';
                container.style.background = 'rgba(255, 255, 255, 0.05)';
            }
        });

        // Hide audio controls
        const audioControls = document.getElementById('audioControls');
        const startNewBtn = document.getElementById('startNewInterview');
        if (audioControls) audioControls.classList.add('hidden');
        if (startNewBtn) startNewBtn.classList.add('hidden');
        
        // Reset state
        this.currentQuestionIndex = 0;
        this.questions = [];
        this.qaPairs = [];
        this.candidateInfo = {};
        this.isInterviewActive = false;
        
        // Clear status
        const uploadStatus = document.getElementById('uploadStatus');
        if (uploadStatus) uploadStatus.innerHTML = '';
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    showStatus(type, message) {
        const statusDiv = document.getElementById('uploadStatus');
        if (statusDiv) {
            statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
            
            setTimeout(() => {
                statusDiv.innerHTML = '';
            }, 5000);
        }
    }

    // Results Management
    loadResults() {
        try {
            const saved = localStorage.getItem('voiceInterviewResults');
            if (saved) {
                this.results = JSON.parse(saved);
            }
        } catch (error) {
            console.error('Error loading results:', error);
            this.results = [];
        }
    }

    saveResults() {
        try {
            localStorage.setItem('voiceInterviewResults', JSON.stringify(this.results));
        } catch (error) {
            console.error('Error saving results:', error);
        }
    }

    sortResults() {
        const sortByEl = document.getElementById('sortBy');
        if (!sortByEl) return;
        
        const sortBy = sortByEl.value;
        
        this.results.sort((a, b) => {
            switch (sortBy) {
                case 'score':
                    return b.score - a.score;
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'timestamp':
                    return new Date(b.timestamp) - new Date(a.timestamp);
                default:
                    return 0;
            }
        });
        
        this.displayResultsTable();
    }

    displayResultsTable() {
        const container = document.getElementById('resultsContainer');
        if (!container) return;
        
        if (this.results.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>📋 No Interviews Completed Yet</h3>
                    <p>Complete some interviews to see candidate results and rankings here.</p>
                </div>
            `;
            return;
        }

        let tableHTML = `
            <div class="results-table">
                <div class="table-header">
                    <div>Candidate Details</div>
                    <div>Overall Score</div>
                    <div>Interview Date</div>
                    <div>Actions</div>
                </div>
        `;

        this.results.forEach((result, index) => {
            const date = new Date(result.timestamp).toLocaleDateString();
            const scoreBadgeClass = this.getScoreBadgeClass(result.score);
            
            tableHTML += `
                <div class="table-row" data-index="${index}">
                    <div>
                        <strong>${result.name}</strong><br>
                        <small style="opacity: 0.7;">${result.position || 'Position not specified'}</small><br>
                        <small style="opacity: 0.6;">${result.email || 'Email not provided'}</small>
                    </div>
                    <div>
                        <span class="score-badge ${scoreBadgeClass}">${result.score}%</span>
                    </div>
                    <div>${date}</div>
                    <div class="action-buttons">
                        <button class="btn btn-secondary btn-small" onclick="voiceSystem.viewDetails(${index})">
                            👁️ View
                        </button>
                        <button class="btn btn-danger btn-small" onclick="voiceSystem.deleteResult(${index})">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        });

        tableHTML += '</div>';
        container.innerHTML = tableHTML;
    }

    getScoreBadgeClass(score) {
        if (score >= 80) return 'score-excellent';
        if (score >= 60) return 'score-good';
        return 'score-poor';
    }

    viewDetails(index) {
        const result = this.results[index];
        const categories = result.detailedScores || [];
        const categoryText = categories.length > 0 ? 
            categories.map(cat => `${cat.progress}: ${cat.score}%`).join('\n') :
            'No detailed breakdown available';
            
        alert(`
Candidate: ${result.name}
Position: ${result.position || 'Not specified'}
Email: ${result.email || 'Not provided'}
Overall Score: ${result.score}%
Interview Date: ${new Date(result.timestamp).toLocaleString()}

Category Breakdown:
${categoryText}
        `);
    }

    deleteResult(index) {
        if (confirm('Are you sure you want to delete this interview result?')) {
            this.results.splice(index, 1);
            this.saveResults();
            this.displayResultsTable();
        }
    }
}

// Navigation Functions
function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active class from all nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected section
    const targetSection = document.getElementById(sectionName);
    if (targetSection) targetSection.classList.add('active');
    
    // Add active class to clicked button
    if (event && event.target) {
        event.target.classList.add('active');
    }
    
    // Load results if results section is selected
    if (sectionName === 'results' && window.voiceSystem) {
        window.voiceSystem.displayResultsTable();
    }
}

// Results Dashboard Functions
function refreshResults() {
    voiceSystem.displayResultsTable();
    voiceSystem.showStatus('success', 'Results refreshed successfully');
}

function exportResults() {
    if (voiceSystem.results.length === 0) {
        alert('No results to export');
        return;
    }

    const csvContent = [
        ['Name', 'Email', 'Position', 'Overall Score', 'Interview Date'],
        ...voiceSystem.results.map(result => [
            result.name,
            result.email || '',
            result.position || '',
            result.score,
            new Date(result.timestamp).toLocaleDateString()
        ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'interview_results.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}

function clearAllResults() {
    if (confirm('Are you sure you want to delete all interview results? This action cannot be undone.')) {
        voiceSystem.results = [];
        voiceSystem.saveResults();
        voiceSystem.displayResultsTable();
        voiceSystem.showStatus('success', 'All results cleared successfully');
    }
}

// Initialize the system
let voiceSystem;
document.addEventListener('DOMContentLoaded', () => {
    voiceSystem = new VoiceInterviewSystem();
});