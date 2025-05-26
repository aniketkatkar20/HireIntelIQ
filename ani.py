import os
import json
import time
from pathlib import Path
import pyttsx3
import speech_recognition as sr
from google import genai
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog
from docx import Document
import PyPDF2

# Load environment variables
def load_env():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env file")
    return api_key

# Initialize Gemini client
def init_gemini():
    api_key = load_env()
    client = genai.Client(api_key=api_key)
    return client

# Extract text from different file types
def extract_text(path: str) -> str:
    ext = path.lower().split('.')[-1]
    if ext == "txt":
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    elif ext == "pdf":
        text = ""
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
        return text
    elif ext == "docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Unsupported file type. Please upload a .txt, .pdf, or .docx")

# Gemini functions
def generate_questions(client, resume: str, jd: str, n: int = 6) -> list[str]:
    prompt = (
        f"Given the following résumé:\n{resume}\n\n"
        f"And the following job description:\n{jd}\n\n"
        f"Your task is to generate the top {n} most relevant interview questions tailored to the candidate’s skill and experience level, and aligned with the job requirements.\n\n"
        "Instructions:\n"
        "1. Carefully analyze the résumé to determine the candidate's level (e.g., fresher, intermediate, experienced).\n"
        "2. Match the question difficulty and content appropriately.\n\n"
        f"Return only a cleanly numbered list of the top {n} concise, high-quality questions."
    )
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = resp.text.strip()
    questions = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('.', 1)
        q = parts[1].strip() if len(parts) > 1 else line
        questions.append(q)
        if len(questions) >= n:
            break
    return questions

def follow_up_question(client, history: list[dict]) -> str:
    prompt = "Based on the following Q&A history, generate the next best interview question. Return only the question text."
    for i, qa in enumerate(history, start=1):
        prompt += f"\n{i}. Q: {qa['question']} A: {qa['answer']}"
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    return resp.text.strip()

def score_history(client, history: list[dict]) -> str:
    prompt = (
        "You are given a series of interview questions and answers, along with the candidate’s résumé and the job description.\n"
        "Evaluate each answer based on how well it aligns with the candidate's experience level and the expectations of the job role.\n"
        "Respond only in strict JSON format: { 'scores': [int, ...], 'feedback': str }"
    )
    prompt += "\nHistory:" + json.dumps(history, indent=2)
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    return resp.text.strip()

# TTS
class TTSSpeaker:
    def __init__(self):
        self.engine = pyttsx3.init()
    def speak(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()

# STT
class STTListener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
    def listen(self) -> str:
        with sr.Microphone() as mic:
            print("🎤 Listening for your answer... (say 'okay done' to finish)")
            self.recognizer.adjust_for_ambient_noise(mic)
            audio = self.recognizer.listen(mic, timeout=None)
            try:
                text = self.recognizer.recognize_sphinx(audio)
                return text
            except sr.UnknownValueError:
                print("⚠ Could not understand audio. Please repeat.")
                return ""
            except sr.RequestError as e:
                print(f"⚠ STT service error: {e}")
                return ""

# Save Q&A
def save_history(history: list[dict], path: str):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        print(f"History saved to: {path}")
    except Exception as e:
        print(f"⚠ Error saving history: {e}")

# Main pipeline
def run_qna_pipeline(resume_path: str, jd_path: str, history_path: str):
    client = init_gemini()
    tts = TTSSpeaker()
    stt = STTListener()

    resume = extract_text(resume_path)
    jd = extract_text(jd_path)

    questions = generate_questions(client, resume, jd)
    history = []

    try:
        for q in questions:
            tts.speak(q)
            print("Q:", q)
            ans = stt.listen()
            if not ans:
                continue
            print("A:", ans)
            if "okay done" in ans.lower():
                print("Interview session ended by user.")
                break
            history.append({"question": q, "answer": ans})

        while True:
            next_q = follow_up_question(client, history)
            if next_q.lower() in ("done", "no more", "stop"):
                print("Interview session ended by AI.")
                break
            tts.speak(next_q)
            print("Q:", next_q)
            ans = stt.listen()
            if not ans:
                continue
            print("A:", ans)
            if "okay done" in ans.lower():
                print("Interview session ended by user.")
                break
            history.append({"question": next_q, "answer": ans})
    finally:
        save_history(history, history_path)

    result = score_history(client, history)
    print("\nFinal Evaluation:", result)

# Entry point
if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)

    # GUI file picker
    root = tk.Tk()
    root.withdraw()

    print("Please select your RESUME file (.txt, .pdf, .docx)...")
    resume_file = filedialog.askopenfilename(
        title="Select Resume File",
        filetypes=[("Supported files", "*.txt *.pdf *.docx")]
    )

    if not resume_file:
        print("No resume file selected. Exiting.")
        exit(1)

    print("Please select the JOB DESCRIPTION file (.txt, .pdf, .docx)...")
    jd_file = filedialog.askopenfilename(
        title="Select Job Description File",
        filetypes=[("Supported files", "*.txt *.pdf *.docx")]
    )

    if not jd_file:
        print("No job description file selected. Exiting.")
        exit(1)

    history_file = "data/history.json"

    run_qna_pipeline(resume_file, jd_file, history_file)

