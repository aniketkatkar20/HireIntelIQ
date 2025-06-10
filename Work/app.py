from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
import csv
import io
from datetime import datetime
from main import run_qna_pipeline
from scorer import get_similarity_scores, evaluate_qa_pairs
import csv
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage
from audio_detector import AudioDetector, VoiceRegistrationError
import atexit
import threading



app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# File paths
TOP_FILE = 'data/top.json'
RESULTS_FILE = 'data/interview_results.json'
SESSIONS_FILE = 'data/active_sessions.json'

# Initialize data files if they don't exist
def initialize_data_files():
    if not os.path.exists(TOP_FILE):
        with open(TOP_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'w') as f:
            json.dump({}, f)

initialize_data_files()

def initialize_audio_detector():
    """Initialize the enhanced audio detector with voice registration"""
    global audio_detector
    
    def warning_handler(count, max_warnings, violation_type):
        print(f"⚠️  Voice Detection Warning {count}/{max_warnings}: {violation_type}")
        # Store warning in session data for frontend
        try:
            warning_data = {
                'count': count,
                'max_warnings': max_warnings,
                'violation_type': violation_type,
                'timestamp': datetime.now().isoformat()
            }
            with open('data/current_warnings.json', 'w') as f:
                json.dump(warning_data, f)
        except Exception as e:
            print(f"Error storing warning data: {e}")
    
    def cancel_handler(reason):
        print(f"❌ Interview cancelled due to: {reason}")
        try:
            # Update interview status in session
            with open('data/interview_status.json', 'w') as f:
                json.dump({
                    'status': 'cancelled',
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            print(f"Error updating interview status: {e}")
    
    def malpractice_handler(count, max_attempts):
        print(f"🚨 MALPRACTICE ATTEMPT {count}/{max_attempts}: Multiple violations detected!")
        try:
            malpractice_data = {
                'count': count,
                'max_attempts': max_attempts,
                'timestamp': datetime.now().isoformat()
            }
            with open('data/malpractice_status.json', 'w') as f:
                json.dump(malpractice_data, f)
        except Exception as e:
            print(f"Error storing malpractice data: {e}")
    
    try:
        audio_detector = AudioDetector(
            warning_callback=warning_handler,
            cancel_callback=cancel_handler,
            malpractice_callback=malpractice_handler
        )
        print("🎤 Enhanced audio detector with voice registration initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize audio detector: {e}")
        return False

# Initialize audio detector
audio_available = initialize_audio_detector()

# Add cleanup function
def cleanup_audio():
    """Cleanup audio detector on app shutdown"""
    global audio_detector
    if audio_detector:
        audio_detector.cleanup()
        print("🔧 Audio detector cleaned up")

# Register cleanup function
atexit.register(cleanup_audio)

# ===== NEW VOICE REGISTRATION ENDPOINTS =====

@app.route('/check-audio-availability', methods=['GET'])
def check_audio_availability():
    """Check if audio input device is available"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'error',
            'available': False,
            'message': 'Audio detector not initialized'
        })
    
    try:
        available = audio_detector.is_audio_device_available()
        return jsonify({
            'status': 'success',
            'available': available,
            'message': 'Audio device available' if available else 'No audio input device detected'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'available': False,
            'message': str(e)
        })

@app.route('/start-voice-registration', methods=['POST'])
def start_voice_registration():
    """Start voice registration process"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'error',
            'message': 'Audio detector not available'
        })
    
    try:
        data = request.get_json() if request.is_json else {}
        duration = data.get('duration', 10)  # Default 10 seconds
        
        # Check if audio device is available
        if not audio_detector.is_audio_device_available():
            return jsonify({
                'status': 'error',
                'message': 'No audio input device detected. Please check your microphone.'
            })
        
        # Start voice registration in a separate thread
        def registration_worker():
            try:
                registration_thread = audio_detector.start_voice_registration(duration)
                registration_thread.join()  # Wait for registration to complete
                
                # Update registration status
                with open('data/registration_status.json', 'w') as f:
                    json.dump({
                        'status': 'completed',
                        'success': audio_detector.is_voice_registered,
                        'timestamp': datetime.now().isoformat()
                    }, f)
                    
            except VoiceRegistrationError as e:
                with open('data/registration_status.json', 'w') as f:
                    json.dump({
                        'status': 'failed',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }, f)
            except Exception as e:
                with open('data/registration_status.json', 'w') as f:
                    json.dump({
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }, f)
        
        # Set initial status
        with open('data/registration_status.json', 'w') as f:
            json.dump({
                'status': 'recording',
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            }, f)
        
        # Start registration thread
        reg_thread = threading.Thread(target=registration_worker)
        reg_thread.daemon = True
        reg_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': f'Voice registration started for {duration} seconds',
            'duration': duration
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to start voice registration: {str(e)}'
        })

@app.route('/check-registration-status', methods=['GET'])
def check_registration_status():
    """Check voice registration status"""
    try:
        status_file = 'data/registration_status.json'
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status = json.load(f)
            return jsonify({'status': 'success', 'registration': status})
        else:
            return jsonify({
                'status': 'success',
                'registration': {'status': 'not_started'}
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/load-voice-profile', methods=['POST'])
def load_voice_profile():
    """Load existing voice profile"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'error',
            'message': 'Audio detector not available'
        })
    
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'status': 'error',
                'message': 'Session ID required'
            })
        
        success = audio_detector.load_voice_registration(session_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Voice profile loaded for session {session_id}',
                'is_registered': True
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to load voice profile'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get-voice-profiles', methods=['GET'])
def get_voice_profiles():
    """Get list of available voice profiles"""
    try:
        profiles_dir = 'data/voice_profiles'
        if not os.path.exists(profiles_dir):
            return jsonify({'status': 'success', 'profiles': []})
        
        profiles = []
        for filename in os.listdir(profiles_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(profiles_dir, filename), 'r') as f:
                        profile_data = json.load(f)
                    
                    profiles.append({
                        'session_id': profile_data['session_id'],
                        'timestamp': profile_data['timestamp'],
                        'filename': filename
                    })
                except Exception as e:
                    print(f"Error reading profile {filename}: {e}")
        
        # Sort by timestamp (newest first)
        profiles.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'status': 'success', 'profiles': profiles})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/test-voice-registration', methods=['POST'])
def test_voice_registration():
    """Test voice registration with shorter duration"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'error',
            'message': 'Audio detector not available'
        })
    
    try:
        data = request.get_json() if request.is_json else {}
        duration = data.get('duration', 5)  # Default 5 seconds for testing
        
        success = audio_detector.test_voice_registration(duration)
        
        return jsonify({
            'status': 'success' if success else 'failed',
            'message': 'Voice registration test completed',
            'success': success,
            'is_registered': audio_detector.is_voice_registered
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

# ===== UPDATED MONITORING ENDPOINTS =====

@app.route('/start-audio-monitoring', methods=['POST'])
def start_audio_monitoring():
    """Start audio monitoring before interview"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'error', 
            'message': 'Audio detector not available'
        })
    
    try:
        # Check if voice is registered
        if not audio_detector.is_voice_registered:
            return jsonify({
                'status': 'error',
                'message': 'Voice must be registered before starting monitoring'
            })
        
        # Check if audio device is available
        if not audio_detector.is_audio_device_available():
            return jsonify({
                'status': 'error',
                'message': 'No audio input device detected. Please check your microphone.'
            })
        
        # Start monitoring
        audio_detector.start_monitoring()
        
        return jsonify({
            'status': 'success',
            'message': 'Audio monitoring started with voice verification'
        })
        
    except VoiceRegistrationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to start audio monitoring: {str(e)}'
        })

@app.route('/stop-audio-monitoring', methods=['POST'])
def stop_audio_monitoring():
    """Stop audio monitoring"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({'status': 'error', 'message': 'Audio detector not available'})
    
    try:
        audio_detector.stop_monitoring()
        return jsonify({'status': 'success', 'message': 'Audio monitoring stopped'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/start-interview-monitoring', methods=['POST'])
def start_interview_monitoring():
    """Start interview-specific monitoring"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({'status': 'error', 'message': 'Audio detector not available'})
    
    try:
        audio_detector.start_interview()
        return jsonify({
            'status': 'success',
            'message': 'Interview monitoring started with voice verification'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/end-interview-monitoring', methods=['POST'])
def end_interview_monitoring():
    """End interview monitoring"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({'status': 'success', 'message': 'No active monitoring'})
    
    try:
        audio_detector.end_interview()
        return jsonify({'status': 'success', 'message': 'Interview monitoring ended'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-voice-warnings', methods=['GET'])
def get_voice_warnings():
    """Get current voice warning and malpractice counts"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({
            'status': 'success', 
            'warnings': 0, 
            'max_warnings': 3,
            'malpractice_count': 0,
            'max_malpractice': 5
        })
    
    try:
        return jsonify({
            'status': 'success',
            'warnings': audio_detector.get_warning_count(),
            'max_warnings': audio_detector.max_warnings,
            'malpractice_count': audio_detector.get_malpractice_count(),
            'max_malpractice': audio_detector.max_malpractice_attempts,
            'is_registered': audio_detector.is_voice_registered
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/reset-voice-warnings', methods=['POST'])
def reset_voice_warnings():
    """Reset voice warning count"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({'status': 'success', 'message': 'No detector to reset'})
    
    try:
        audio_detector.reset_warnings()
        return jsonify({'status': 'success', 'message': 'Warnings reset'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-malpractice-log', methods=['GET'])
def get_malpractice_log():
    """Get malpractice log"""
    global audio_detector
    
    if not audio_detector:
        return jsonify({'status': 'success', 'log': []})
    
    try:
        log = audio_detector.get_malpractice_log()
        return jsonify({'status': 'success', 'log': log})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/check-interview-status', methods=['GET'])
def check_interview_status():
    """Check if interview was cancelled due to voice detection"""
    try:
        status_file = 'data/interview_status.json'
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status = json.load(f)
            return jsonify({'status': 'success', 'interview_status': status})
        else:
            return jsonify({
                'status': 'success', 
                'interview_status': {'status': 'active'}
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ===== EXISTING ENDPOINTS =====

@app.route('/')
def index():
    return render_template('index.html')

def index():
    # Since your HTML is complete, we'll serve it directly
    # Copy your HTML content to templates/index.html
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        resume = request.files['resume']
        jd = request.files['jd']

        if not resume or not jd:
            return jsonify({"status": "error", "message": "Both resume and job description files are required"})

        # Validate file types
        allowed_extensions = {'pdf', 'docx', 'txt'}
        resume_ext = resume.filename.rsplit('.', 1)[1].lower() if '.' in resume.filename else ''
        jd_ext = jd.filename.rsplit('.', 1)[1].lower() if '.' in jd.filename else ''
        
        if resume_ext not in allowed_extensions or jd_ext not in allowed_extensions:
            return jsonify({"status": "error", "message": "Only PDF, DOCX, and TXT files are allowed"})

        resume_filename = secure_filename(resume.filename)
        jd_filename = secure_filename(jd.filename)

        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        resume_filename = f"{timestamp}_{resume_filename}"
        jd_filename = f"{timestamp}_{jd_filename}"

        resume_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_filename)
        jd_path = os.path.join(app.config['UPLOAD_FOLDER'], jd_filename)

        resume.save(resume_path)
        jd.save(jd_path)

        # Store file paths for current session
        session_data = {
            "resume": resume_path, 
            "jd": jd_path,
            "timestamp": timestamp
        }
        
        with open('data/latest_files.json', 'w') as f:
            json.dump(session_data, f)

        # Clean up old transcript
        transcript_path = os.path.join('data', 'transcript.txt')
        if os.path.exists(transcript_path):
            os.remove(transcript_path)

        # Generate questions
        history_path = os.path.join('data', 'history.json')
        result = run_qna_pipeline(resume_path, jd_path, history_path, flask_mode=True)

        return jsonify({
            "status": "success",
            "result": result,
            "message": "Files uploaded and questions generated successfully"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Upload failed: {str(e)}"})

def start_voice():
    try:
        history_path = os.path.join("data", "history.json")
        if not os.path.exists(history_path):
            return jsonify({"status": "error", "message": "No questions available. Please upload files first."})

        with open(history_path, "r") as f:
            history = json.load(f)

        # Find next unanswered question
        for item in history:
            if item.get("answer") == "<user_input_required>":
                
                # Start interview monitoring when first question is served
                global audio_detector
                if audio_detector and audio_detector.is_voice_registered:
                    try:
                        audio_detector.start_interview()
                    except Exception as e:
                        print(f"Warning: Could not start audio monitoring: {e}")
                
                return jsonify({"status": "success", "question": item["question"]})

        return jsonify({"status": "done", "message": "All questions answered."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})

@app.route("/save-transcript", methods=["POST"])
def save_transcript():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        answer = data.get("answer", "").strip()

        if not question:
            return jsonify({"status": "error", "message": "Missing question"}), 400

        # Append to transcript file
        with open("data/transcript.txt", "a", encoding="utf-8") as f:
            f.write(f"Q: {question}\nA: {answer}\n\n")

        # Update history file
        history_path = "data/history.json"
        if os.path.exists(history_path):
            with open(history_path, "r") as f:
                history = json.load(f)

            # Find and update the corresponding question
            for item in history:
                if item["question"].strip() == question.strip():
                    item["answer"] = answer
                    break

            with open(history_path, "w") as f:
                json.dump(history, f, indent=2)

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
def generate_category_scores(base_score):
    """Generate realistic category scores based on overall score"""
    import random
    categories = [
        'Technical Knowledge',
        'Communication Skills', 
        'Problem Solving',
        'Relevant Experience',
        'Cultural Fit'
    ]
    
    scores = []
    for category in categories:
        # Add some variance to make it realistic
        variance = random.uniform(-0.15, 0.15)
        category_score = max(0, min(1, base_score + variance))
        scores.append({
            'name': category,
            'score': round(category_score * 100, 1)
        })
    
    return scores

def update_top_candidates(name, score):
    """Update the top candidates list"""
    try:
        with open(TOP_FILE, 'r') as f:
            top_candidates = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        top_candidates = []

    # Add new candidate
    top_candidates.append({
        'name': name, 
        'score': round(score * 100, 1),
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only top 10, sorted by score
    top_candidates = sorted(top_candidates, key=lambda x: x['score'], reverse=True)[:10]

    with open(TOP_FILE, 'w') as f:
        json.dump(top_candidates, f, indent=2)

def save_detailed_transcript(name, email, position, score, qa_pairs):
    """Save detailed interview transcript"""
    with open("data/transcript.txt", "a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"INTERVIEW TRANSCRIPT\n")
        f.write(f"Candidate: {name}\n")
        f.write(f"Email: {email}\n")
        f.write(f"Position: {position}\n")
        f.write(f"Overall Score: {round(score * 100, 1)}%\n")
        f.write(f"Interview Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, pair in enumerate(qa_pairs, 1):
            f.write(f"Question {i}: {pair['question']}\n")
            f.write(f"Answer {i}: {pair['answer']}\n")
            f.write("-" * 40 + "\n")
        
        f.write("\n" + "=" * 80 + "\n\n")

@app.route('/get-results', methods=['GET'])
def get_results():
    """Get all interview results for the dashboard"""
    try:
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
        
        # Sort by timestamp (most recent first)
        results = sorted(results, key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'status': 'success', 'results': results})
        
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'status': 'success', 'results': []})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/delete-result/<result_id>', methods=['DELETE'])
def delete_result(result_id):
    """Delete a specific interview result"""
    try:
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
        
        # Filter out the result to delete
        results = [r for r in results if r['id'] != result_id]
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Result deleted successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/clear-all-results', methods=['DELETE'])
def clear_all_results():
    """Clear all interview results"""
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump([], f)
        
        with open(TOP_FILE, 'w') as f:
            json.dump([], f)
            
        return jsonify({'status': 'success', 'message': 'All results cleared successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/export-results')
def export_results():
    """Export results as CSV"""
    try:
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Name', 'Email', 'Position', 'Overall Score (%)', 'Interview Date', 'Technical Knowledge (%)', 'Communication Skills (%)', 'Problem Solving (%)', 'Relevant Experience (%)', 'Cultural Fit (%)'])
        
        # Write data
        for result in results:
            date = datetime.fromisoformat(result['timestamp']).strftime('%Y-%m-%d %H:%M')
            categories = {cat['name']: cat['score'] for cat in result.get('categories', [])}
            
            writer.writerow([
                result['name'],
                result.get('email', ''),
                result.get('position', ''),
                round(result['score'] * 100, 1),
                date,
                categories.get('Technical Knowledge', ''),
                categories.get('Communication Skills', ''),
                categories.get('Problem Solving', ''),
                categories.get('Relevant Experience', ''),
                categories.get('Cultural Fit', '')
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'interview_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/top-candidates', methods=['GET'])
def top_candidates():
    """Get top candidates"""
    try:
        with open(TOP_FILE, 'r') as f:
            top = json.load(f)
        return jsonify({'status': 'success', 'candidates': top})
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({'status': 'success', 'candidates': []})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/score-transcript', methods=['GET'])
def score_transcript():
    """Score existing transcript (legacy endpoint)"""
    try:
        transcript_path = os.path.join("data", "transcript.txt")
        if not os.path.exists(transcript_path):
            return jsonify({"status": "error", "message": "No transcript found"})

        scores = get_similarity_scores(transcript_path)

        with open(os.path.join("data", "output.json"), "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2)

        return jsonify({'status': 'success', 'scores': scores})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.errorhandler(413)
def too_large(e):
    return jsonify({'status': 'error', 'message': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500



load_dotenv()

def export_results_to_csv(results, filename='data/hr_results.csv'):
    with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        header = ['ID', 'Name', 'Email', 'Position', 'Score', 'Timestamp']
        writer.writerow(header)
        for r in results:
            writer.writerow([
                r.get('id'), r.get('name'), r.get('email'),
                r.get('position'), r.get('score'), r.get('timestamp')
            ])
    return filename
def send_email_with_csv(to_email, subject, body, attachment_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_ADDRESS')
    msg['To'] = to_email
    msg.set_content(body)

    # Attach the CSV file
    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)
    msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

    # Send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))
        smtp.send_message(msg)

@app.route('/submit-result', methods=['POST'])
def submit_result():
    try:
        new_result = request.json  # or use request.form if form submission
        results = []

        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)

        results.append(new_result)

        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=4)

        # ✅ Export to CSV
        csv_path = export_results_to_csv(results)

        # ✅ Send Email Immediately After Interview
        send_email_with_csv(
            to_email=os.getenv('HR_EMAIL'),
            subject='New Interview Result Submitted',
            body='A new interview result has been submitted. Please find the attached CSV with all current results.',
            attachment_path=csv_path
        )

        return jsonify({'status': 'success', 'message': 'Result submitted and email sent.'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)})


if __name__ == '__main__':
    print("Starting HireIntelIQ Voice Interview System...")
    print("Available endpoints:")
    print("  - / (Interview Interface)")
    print("  - /upload (File Upload)")
    print("  - /submit-interview (Submit Interview)")
    print("  - /get-results (Get Results)")
    print("  - /top-candidates (Top Candidates)")
    print("  - /export-results (Export CSV)")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
