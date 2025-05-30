from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
from main import run_qna_pipeline
from scorer import get_similarity_scores

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        print("=== UPLOAD ENDPOINT CALLED ===")
        resume = request.files['resume']
        jd = request.files['jd']

        print(f"Resume file: {resume.filename}")
        print(f"JD file: {jd.filename}")

        resume_filename = secure_filename(resume.filename)
        jd_filename = secure_filename(jd.filename)

        resume_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_filename)
        jd_path = os.path.join(app.config['UPLOAD_FOLDER'], jd_filename)

        resume.save(resume_path)
        jd.save(jd_path)
        print(f"Files saved to: {resume_path}, {jd_path}")

        # Save latest file paths for use in /start-voice
        with open('data/latest_files.json', 'w') as f:
            json.dump({"resume": resume_path, "jd": jd_path}, f)

        history_path = os.path.join('data', 'history.json')
        
        # Clear previous transcript
        transcript_path = os.path.join('data', 'transcript.txt')
        if os.path.exists(transcript_path):
            os.remove(transcript_path)
            print("Previous transcript cleared")

        print("Running QnA pipeline...")
        # Run the QnA pipeline
        result = run_qna_pipeline(resume_path, jd_path, history_path, flask_mode=True)
        
        print(f"Pipeline result: {result}")  # Debug print
        print(f"Result type: {type(result)}")
        
        # Check if history file was created
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                history = json.load(f)
            print(f"History file created with {len(history)} questions")
        else:
            print("ERROR: History file was not created!")
        
        return jsonify({
            "status": "success",
            "result": result,  # Don't parse as JSON, it's already a dict
            "message": "Files uploaded and questions generated successfully"
        })

    except Exception as e:
        print(f"Upload error: {str(e)}")  # Debug print
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})

@app.route("/start-voice")
def start_voice():
    try:
        print("=== START-VOICE ENDPOINT CALLED ===")
        history_path = os.path.join("data", "history.json")
        print(f"Looking for history file at: {history_path}")
        print(f"History file exists: {os.path.exists(history_path)}")
        
        # List all files in data directory
        data_dir = "data"
        if os.path.exists(data_dir):
            files = os.listdir(data_dir)
            print(f"Files in data directory: {files}")
        else:
            print("Data directory does not exist")
            os.makedirs(data_dir, exist_ok=True)
        
        # Check if history file exists
        if not os.path.exists(history_path):
            print("History file not found, returning error")
            return jsonify({"status": "error", "message": "No questions available. Please upload files first."})
        
        with open(history_path, "r") as f:
            history = json.load(f)
        
        print(f"History loaded with {len(history)} items")
        for i, item in enumerate(history):
            print(f"Question {i+1}: {item.get('question', '')[:50]}...")
            print(f"Answer {i+1}: {item.get('answer', '')}")

        # Find first unanswered question
        for item in history:
            if item.get("answer") == "<user_input_required>":
                print(f"Found unanswered question: {item['question'][:50]}...")
                return jsonify({"status": "success", "question": item["question"]})

        print("All questions answered")
        return jsonify({"status": "done", "message": "All questions answered."})

    except FileNotFoundError as e:
        print(f"File not found error: {str(e)}")
        return jsonify({"status": "error", "message": "History file not found. Please upload files first."})
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return jsonify({"status": "error", "message": "Invalid history file format."})
    except Exception as e:
        print(f"Start-voice error: {str(e)}")  # Debug print
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

        print(f"Saving transcript - Q: {question[:50]}... A: {answer[:50]}...")  # Debug print

        # Save to transcript file
        with open("data/transcript.txt", "a", encoding="utf-8") as f:
            f.write(f"Q: {question}\nA: {answer}\n\n")

        # Update history.json
        history_path = "data/history.json"
        if os.path.exists(history_path):
            with open(history_path, "r") as f:
                history = json.load(f)

            # Find and update the question
            for item in history:
                if item["question"].strip() == question.strip():
                    item["answer"] = answer
                    break

            with open(history_path, "w") as f:
                json.dump(history, f, indent=2)

        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Save transcript error: {str(e)}")  # Debug print
        return jsonify({"status": "error", "message": str(e)})

@app.route('/score-transcript', methods=['GET'])
def score_transcript():
    try:
        transcript_path = os.path.join("data", "transcript.txt")
        
        if not os.path.exists(transcript_path):
            return jsonify({"status": "error", "message": "No transcript found"})
        
        scores = get_similarity_scores(transcript_path)

        with open(os.path.join("data", "output.json"), "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2)

        return jsonify({'status': 'success', 'scores': scores})
    except Exception as e:
        print(f"Score transcript error: {str(e)}")  # Debug print
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)