# === Backend Logic ===
import time
import uuid
from groq import Groq
import textwrap
import base64
import pyttsx3
import numpy as np
import random
from datetime import datetime
import threading
import tempfile
from gtts import gTTS
import os
from faster_whisper import WhisperModel
from scipy.io.wavfile import write
from io import BytesIO
import sounddevice as sd
import subprocess
import pygame
import streamlit as st
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

GROQ_API_KEY = "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"

recording_active = False
recording_lock = threading.Lock()


def get_robot_logo_html():
    robot_logo = """
    <div class="logo-container">
        <div class="robot-logo">
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="120" height="120" rx="60" fill="#EFF6FF"/>
                <rect x="30" y="30" width="60" height="60" rx="15" fill="#3B82F6"/>
                <circle cx="45" cy="50" r="5" fill="white"/>
                <circle cx="75" cy="50" r="5" fill="white"/>
                <rect x="45" y="70" width="30" height="5" rx="2.5" fill="white"/>
                <rect x="25" y="25" width="10" height="20" rx="5" fill="#F59E0B"/>
                <rect x="85" y="25" width="10" height="20" rx="5" fill="#F59E0B"/>
            </svg>
        </div>
    </div>
    """
    return robot_logo

# ========== UTILITY FUNCTIONS ==========
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

DEFAULT_WHISPER_MODEL_SIZE = "tiny.en"
@st.cache_resource
def load_whisper():
    return WhisperModel(DEFAULT_WHISPER_MODEL_SIZE, compute_type="int8")

whisper = load_whisper()

# ========== SESSION STATE ========== 
default_state = {
    "current_question": "",
    "question_number": 0,
    "scores": [],
    "domain": "Python",
    "finished": False,
    "answered": False,
    "interview_started": False,
    "spoken": False,
    "recording_started": False,
    "audio_recording_filename": "temp.wav",
    "audio_thread": None,
    "recording_start_time": None,
    "transcript": "",
    "feedback": "",
    "score": 0,
    "page": "intro",  # intro -> setup -> interview -> result
    "interview_in_progress": False,
    "recording_duration": 0,  # No fixed limit - will be controlled by user
    "interview_ended": False,
    "username": "",
    "questions_asked": 0,
    "total_score": 0,
    # Code-related variables
    "is_coding_question": False,
    "code_submission": "",
    "code_language": "python",
    "code_result": None,
    "code_feedback": "",
    "supported_languages": ["python", "java", "javascript", "cpp", "html", "css"],  # Supported languages
    "read_question_aloud": False  # New variable to control auto-reading
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ========== CORE FUNCTIONS ==========
def speak_sync(text, slow=False, rate=2):
    """
    Function to convert English text to speech with Indian accent/voice
    
    Parameters:
        text (str): The English text to convert to speech
        slow (bool): Whether to use the slow TTS option (defaults to False for normal speed)
        rate (float): Playback rate modifier (1.0 is normal, >1.0 is faster, <1.0 is slower)
                     Only works if pygame mixer supports it
    """
    try:
        # Use English language with standard TLD for more natural speed
        # Set slow=False to ensure normal speed base
        tts = gTTS(text=text, lang='en', tld='com', slow=False)
        
        # Save to a BytesIO object (memory) instead of a file
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        # Initialize pygame mixer
        pygame.mixer.init(frequency=24000)  # Higher frequency for faster playback
        
        # Load the audio file and play it
        pygame.mixer.music.load(fp)
        pygame.mixer.music.play()
        
        # Wait for the audio to finish playing
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
    except Exception as e:
        print(f"TTS Error: {str(e)}")

def speak_question():
    """
    Function to speak the current question using text-to-speech
    Only triggered when the speak aloud button is clicked
    """
    if not st.session_state.read_question_aloud:
        return
    if st.session_state.current_question:
        # Reset spoken flag to False so we can speak again if needed
        st.session_state.spoken = False
        
        # Create a thread to speak the question so it doesn't block the UI
        speech_thread = threading.Thread(
            target=speak_sync,
            args=(st.session_state.current_question,)
        )
        speech_thread.start()
        st.session_state.spoken = True
def on_speak_button_click():
    """
    Function to handle the speak aloud button click
    """
    st.session_state.read_question_aloud = True
    speak_question()

def on_stop_speak_button_click():
    """
    Function to handle the stop speak button click
    """
    st.session_state.read_question_aloud = False
    try:
        pygame.mixer.music.stop()
    except:
        pass

SAMPLE_RATE = 16000  # Default sample rate for Whisper and sounddevice


def _record(filename):
    """
    Record audio to a file until manually stopped - FIXED VERSION
    """
    global recording_active
    
    try:
        # Create a new recording stream with proper buffer settings
        recording = sd.InputStream(
            samplerate=SAMPLE_RATE, 
            channels=1, 
            dtype='int16',
            blocksize=1024,  # Add buffer size
            latency='low'     # Reduce latency
        )
        recording.start()
        
        frames = []
        
        # Continue recording while the flag is True
        while recording_active:
            try:
                audio, overflowed = recording.read(1024)  # Read in chunks
                if overflowed:
                    print("Audio buffer overflow detected")
                
                if len(audio) > 0:
                    frames.append(audio.copy())
                
                time.sleep(0.01)  # Smaller sleep for better responsiveness
            except Exception as read_error:
                print(f"Error reading audio: {read_error}")
                break
        
        # Stop and close the recording when done
        recording.stop()
        recording.close()
        
        # Save the recorded audio data
        if len(frames) > 0:
            audio_data = np.concatenate(frames, axis=0)
            # Ensure we have enough audio data (at least 1 second)
            if len(audio_data) > SAMPLE_RATE * 0.5:  # At least 0.5 seconds
                write(filename, SAMPLE_RATE, audio_data)
                print(f"Audio saved successfully: {filename}, Duration: {len(audio_data)/SAMPLE_RATE:.2f}s")
                return True
            else:
                print(f"Audio too short: {len(audio_data)/SAMPLE_RATE:.2f}s")
                return False
        
        print("No audio frames recorded")
        return False
        
    except Exception as e:
        print(f"Recording error: {str(e)}")
        return False

def start_recording():
    """
    Start the audio recording in a separate thread - FIXED VERSION
    """
    global recording_active
    
    with recording_lock:
        # Stop any existing recording first
        if recording_active:
            recording_active = False
            time.sleep(0.5)  # Give time for previous recording to stop
        
        # Clean up any existing thread
        if hasattr(st.session_state, 'audio_thread') and st.session_state.audio_thread and st.session_state.audio_thread.is_alive():
            st.session_state.audio_thread.join(timeout=1.0)
        
        # Reset state and prepare filename
        st.session_state.recording_started = True
        st.session_state.recording_start_time = time.time()
        st.session_state.audio_recording_filename = f"temp_q{st.session_state.question_number + 1}_{int(time.time())}.wav"
        
        # Set global recording flag
        recording_active = True
        
        # Start recording in a thread
        thread = threading.Thread(
            target=_record,
            args=(st.session_state.audio_recording_filename,),
            daemon=True
        )
        thread.start()
        
        # Store the thread object in session state
        st.session_state.audio_thread = thread
        
        print("Recording started successfully")


def stop_recording():
    """
    Stop the audio recording and process the result - FIXED VERSION
    """
    global recording_active
    
    with recording_lock:
        # Signal the thread to stop recording
        recording_active = False
        
        # Update the session state
        st.session_state.recording_started = False
        
        # Wait for the recording thread to finish
        if hasattr(st.session_state, 'audio_thread') and st.session_state.audio_thread and st.session_state.audio_thread.is_alive():
            st.session_state.audio_thread.join(timeout=3.0)  # Increased timeout
        
        st.session_state.audio_thread = None
    
    # Small delay to ensure file is written
    time.sleep(0.5)
    
    try:
        # Check if the file exists and has content
        if not os.path.exists(st.session_state.audio_recording_filename):
            st.warning("⚠ Audio file was not created. Please try again.")
            return
            
        file_size = os.path.getsize(st.session_state.audio_recording_filename)
        if file_size == 0:
            st.warning("⚠ No audio was recorded. Please try again.")
            return
        
        print(f"Processing audio file: {st.session_state.audio_recording_filename}, Size: {file_size} bytes")
        
        # Process the recording
        with st.spinner("Transcribing your answer..."):
            transcript = transcribe_audio(st.session_state.audio_recording_filename).strip()
            st.session_state.transcript = transcript
            
            if not transcript or len(transcript) < 3:
                st.warning("⚠ No clear voice detected or transcription failed. Please speak louder and try again.")
                return
            
            print(f"Transcription successful: {transcript}")
            
            # Evaluate answer
            with st.spinner("Evaluating your answer..."):
                if st.session_state.is_coding_question:
                    # For coding questions, we shouldn't evaluate audio answers
                    st.warning("This is a coding question. Please submit your code using the code editor.")
                    return
                else:
                    feedback = evaluate_answer(st.session_state.current_question, transcript)
                    score = extract_score(feedback)
                    
                    st.session_state.feedback = feedback
                    st.session_state.score = score
                    st.session_state.scores.append(score)
                    st.session_state.total_score += score
                    st.session_state.questions_asked += 1
                    st.session_state.answered = True
                    st.session_state.finished = True
            
            # Save logs
            os.makedirs("transcripts", exist_ok=True)
            os.makedirs("feedback", exist_ok=True)
            os.makedirs("logs", exist_ok=True)
            
            with open(f"transcripts/q{st.session_state.question_number + 1}.txt", "w", encoding='utf-8') as f:
                f.write(f"Q: {st.session_state.current_question}\nA: {transcript}")
            with open(f"feedback/q{st.session_state.question_number + 1}_feedback.txt", "w", encoding='utf-8') as f:
                f.write(feedback)
            with open("logs/session_log.txt", "a", encoding='utf-8') as log:
                avg_score = sum(st.session_state.scores) / len(st.session_state.scores)
                session_id = uuid.uuid4()
                log.write(f"Session ID: {session_id} | User: {st.session_state.username} | "
                         f"Domain: {st.session_state.domain} | "
                         f"Q{st.session_state.question_number + 1} Score: {score} | Avg: {avg_score:.2f}\n")
            
    except Exception as e:
        st.error(f"❌ Error processing recording: {str(e)}")
        print(f"Error processing recording: {str(e)}")
    finally:
        # Clean up the audio file
        try:
            if os.path.exists(st.session_state.audio_recording_filename):
                os.remove(st.session_state.audio_recording_filename)
        except:
            pass

def transcribe_audio(filename):
    """
    Transcribe audio file with better error handling - FIXED VERSION
    """
    try:
        # Check if file exists and has content
        if not os.path.exists(filename):
            print(f"Audio file does not exist: {filename}")
            return ""
        
        file_size = os.path.getsize(filename)
        if file_size == 0:
            print(f"Audio file is empty: {filename}")
            return ""
        
        print(f"Transcribing audio file: {filename} (Size: {file_size} bytes)")
        
        # Use faster-whisper to transcribe
        segments, info = whisper.transcribe(
            filename,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
            initial_prompt=None,
            word_timestamps=False,
            
            )
        
        transcript_parts = []
        for segment in segments:
            if segment.text.strip():  # Only add non-empty segments
                transcript_parts.append(segment.text.strip())
        
        transcript = " ".join(transcript_parts)
        
        print(f"Transcription result: '{transcript}'")
        print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        return transcript
        
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return ""


def is_recording():
    """
    Check if recording is currently active
    """
    global recording_active
    return recording_active

def cleanup_recording():
    """
    Clean up any ongoing recording and reset states
    """
    global recording_active
    
    with recording_lock:
        recording_active = False
        
        if hasattr(st.session_state, 'audio_thread') and st.session_state.audio_thread:
            if st.session_state.audio_thread.is_alive():
                st.session_state.audio_thread.join(timeout=2.0)
            st.session_state.audio_thread = None
        
        st.session_state.recording_started = False
        


def generate_question(domain):
    apikey=GROQ_API_KEY
    client = Groq(
        api_key=apikey,
    )
    
    # Modified prompt to specifically exclude coding questions
    prompt = f"""Generate one challenging technical interview question related to {domain}.
    
    Important requirements:
    - Make the question specific and thoughtful
    - DO NOT generate any coding questions that ask the candidate to write code
    - DO NOT ask the candidate to implement algorithms or data structures
    - DO NOT ask the candidate to write functions, classes, or any code snippets
    - Focus instead on conceptual understanding, design principles, theory, or system knowledge
    - Questions should test understanding rather than coding ability
    
    Generate a theoretical or conceptual question only."""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False, 
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )
    
    return response.choices[0].message.content.strip()

def evaluate_answer(question, answer):
    apikey=GROQ_API_KEY
    client = Groq(
        api_key=apikey,
    )
    
    # First, check if the answer is relevant to the question
    relevance_prompt = f"""Question: {question}
Answer: {answer}

Analyze if this answer is relevant to the question asked. 
Is the answer attempting to address the question that was asked?
Respond with just "RELEVANT" or "NOT_RELEVANT". 

Guidelines:
- If the answer seems to address the question, even if it's partially correct or incorrect, mark as "RELEVANT"
- If the answer is completely off-topic, discussing something unrelated to the question, mark as "NOT_RELEVANT"
- If the answer is very generic with no specific relation to the question topic, mark as "NOT_RELEVANT"
- If the answer is just repeating the question or contains random text, mark as "NOT_RELEVANT"
"""

    relevance_check = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False,
        messages=[
            {
                "role": "user",
                "content": relevance_prompt,
            }
        ]
    )
    
    relevance_result = relevance_check.choices[0].message.content.strip()
    
    # If the answer is not relevant, return a simple message
    if "NOT_RELEVANT" in relevance_result:
        return "Please give a valid answer that addresses the question. Your response doesn't seem to be related to the question asked."
    
    # If the answer is relevant, proceed with the full evaluation
    # Using a single prompt format for all questions (technical domain questions only)
    prompt = f"""Question: {question}
Answer: {answer}

Evaluate this answer objectively on a scale of 0-10. Provide feedback in the following format:
Score: [0-10]

Strengths:
- [Point 1]
- [Point 2]

Areas for Improvement:
- [Point 1]
- [Point 2]

Overall Feedback: [2-3 sentences with constructive feedback]
"""
    
    feedback = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False, 
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )
    
    return feedback.choices[0].message.content.strip()

# ========== NEW FUNCTIONS FOR CODING QUESTIONS ==========
def generate_coding_question(domain):
    """
    Generate a coding question based on the selected domain
    """
    apikey=GROQ_API_KEY
    client = Groq(
        api_key=apikey,
    )
    
    # Map domain to appropriate language
    language = get_language_from_domain(domain)
    
    prompt = f"""Generate one challenging but practical coding question related to {domain} that uses {language} programming language.
    
    Important requirements:
    - Make the coding question specific, clear, and doable within 10-15 minutes
    - Include a clear problem statement
    - Specify input and expected output formats
    - Make sure it's appropriate for an interview setting
    - Focus on core concepts in {domain}
    - The solution should be implementable in {language}
    - Avoid extremely complex algorithms that would take too long to implement in an interview
    - Do not include the solution in your response
    
    Format your response as:
    
    # Problem Title
    
    ## Problem Statement
    [Clear description of the problem]
    
    ## Input Format
    [Description of input format]
    
    ## Output Format
    [Description of expected output]
    
    ## Example
    Input: [example input]
    Output: [example output]
    
    ## Notes
    [Optional hints or constraints]
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False, 
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )
    
    return response.choices[0].message.content.strip()

def update_default_state():
    supported_languages = [
        "python", 
        "java", 
        "javascript", 
        "cpp", 
        "html", 
        "css"
    ]
    
    return supported_languages
def evaluate_code_submission(question, code, language):
    """
    Evaluate the submitted code using Groq API with language-specific criteria
    """
    apikey=GROQ_API_KEY
    client = Groq(
        api_key=apikey,
    )
    
    # First, check if the code is relevant to the question
    relevance_prompt = f"""Question: {question}
Code Submission ({language}):
{code}

Analyze if this code submission is relevant to the question asked. 
Is the code attempting to solve the problem described in the question?
Respond with just "RELEVANT" or "NOT_RELEVANT".

Guidelines:
- If the code seems to be attempting to solve the problem, even if it's incorrect, mark as "RELEVANT"
- If the code is completely off-topic with no relation to the problem, mark as "NOT_RELEVANT"
- If the code is very generic with no specific relation to the problem, mark as "NOT_RELEVANT"
- If the submission is just random text or code with no apparent purpose, mark as "NOT_RELEVANT"
"""

    relevance_check = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False,
        messages=[
            {
                "role": "user",
                "content": relevance_prompt,
            }
        ]
    )
    
    relevance_result = relevance_check.choices[0].message.content.strip()
    
    # If the code is not relevant, return a simple message
    if "NOT_RELEVANT" in relevance_result:
        return "Please provide code that addresses the problem. Your submission doesn't seem to be related to the question asked."
    
    # Create language-specific guidance for evaluation
    language_guidance = ""
    if language == "python":
        language_guidance = """
- Check if the solution follows Python conventions (PEP 8)
- Check for Pythonic idioms and features like list comprehensions, generators when appropriate
- Evaluate efficiency in terms of time and space complexity
- Check for proper exception handling if applicable
"""
    elif language == "java":
        language_guidance = """
- Check if the solution follows Java conventions and naming standards
- Check for proper OOP principles and design
- Evaluate efficient use of Java collections and native APIs
- Check for proper exception handling if applicable
"""
    elif language == "javascript" or language == "js":
        language_guidance = """
- Check if the solution follows JavaScript best practices
- Assess modern JS features usage (ES6+) when appropriate
- Evaluate asynchronous code handling if applicable
- Check for proper error handling if applicable
"""
    elif language == "cpp" or language == "c++":
        language_guidance = """
- Check if the solution follows C++ conventions and best practices
- Evaluate memory management and potential memory leaks
- Check for efficient use of STL and algorithms
- Evaluate performance considerations
"""
    else:
        language_guidance = """
- Check if the solution follows common coding best practices
- Evaluate algorithmic efficiency
- Check for proper error/exception handling if applicable
"""
    
    prompt = f"""Question: {question}

Submitted Code ({language}):
{language}
{code}


Please evaluate this {language} code submission thoroughly on a scale of 0-10. Provide detailed feedback in the following format:

Score: [0-10]

Correctness:
- [Assess if the code correctly solves the problem]
- [Mention any edge cases missed]

Code Quality:
- [Comment on code style, readability]
- [Assess efficiency and performance]
- [Note any best practices followed or missed]

Language-Specific Assessment:
{language_guidance}

Areas for Improvement:
- [Point 1]
- [Point 2]

Solution Approach:
[Briefly explain a correct solution approach]

Overall Feedback: [2-3 sentences with constructive feedback]
"""
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=False, 
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )
    
    return response.choices[0].message.content.strip()

def run_code(code, language="python"):
    """
    Run the submitted code and return the result based on the programming language
    """
    result = {
        "output": "",
        "error": "",
        "success": False
    }
    
    # Create a temporary file to save the code
    with tempfile.NamedTemporaryFile(suffix=f".{language}", delete=False, mode='w') as temp_file:
        temp_file.write(code)
        temp_filename = temp_file.name
    
    try:
        # Run the code based on the language
        if language == "python":
            # Use subprocess to execute the code
            process = subprocess.run(
                ["python", temp_filename],
                capture_output=True,
                text=True,
                timeout=5  # Set a timeout to prevent infinite loops
            )
            
            if process.returncode == 0:
                result["output"] = process.stdout
                result["success"] = True
            else:
                result["error"] = process.stderr
        
        elif language == "java":
            # For Java, we need to extract the class name, compile and then run
            # Simple class name extraction - this is a basic approach
            class_name = None
            for line in code.split('\n'):
                if 'public class' in line:
                    parts = line.split('public class')[1].strip().split(' ')
                    if parts:
                        class_name = parts[0].strip().split('{')[0].strip()
                        break
            
            if not class_name:
                result["error"] = "Could not identify Java class name. Make sure you have a 'public class ClassName' declaration."
                return result
            
            # Rename temp file to match class name
            java_file = f"{os.path.dirname(temp_filename)}/{class_name}.java"
            os.rename(temp_filename, java_file)
            
            # Compile
            compile_process = subprocess.run(
                ["javac", java_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if compile_process.returncode != 0:
                result["error"] = f"Compilation Error: {compile_process.stderr}"
                return result
            
            # Run
            run_process = subprocess.run(
                ["java", "-cp", os.path.dirname(java_file), class_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if run_process.returncode == 0:
                result["output"] = run_process.stdout
                result["success"] = True
            else:
                result["error"] = f"Runtime Error: {run_process.stderr}"
        
        elif language == "javascript" or language == "js":
            # Run with Node.js
            process = subprocess.run(
                ["node", temp_filename],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if process.returncode == 0:
                result["output"] = process.stdout
                result["success"] = True
            else:
                result["error"] = process.stderr
        
        elif language == "cpp" or language == "c++":
            # Compile C++ code
            compiled_file = f"{os.path.splitext(temp_filename)[0]}"
            compile_process = subprocess.run(
                ["g++", "-std=c++11", temp_filename, "-o", compiled_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if compile_process.returncode != 0:
                result["error"] = f"Compilation Error: {compile_process.stderr}"
                return result
            
            # Run the compiled executable
            run_process = subprocess.run(
                [compiled_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if run_process.returncode == 0:
                result["output"] = run_process.stdout
                result["success"] = True
            else:
                result["error"] = f"Runtime Error: {run_process.stderr}"
                
        elif language == "html":
            # For HTML, there's no execution, so we just return the HTML content
            result["output"] = "HTML code doesn't produce console output. Use a web browser to view."
            result["success"] = True
            
        elif language == "css":
            # Same for CSS
            result["output"] = "CSS code doesn't produce console output. Use a web browser to view with HTML."
            result["success"] = True
            
        else:
            result["error"] = f"Language '{language}' is not supported for execution yet."
    
    except subprocess.TimeoutExpired:
        result["error"] = "Execution timed out. Your code may contain an infinite loop."
    except Exception as e:
        result["error"] = f"An error occurred: {str(e)}"
    
    finally:
        # Clean up the temporary files
        try:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
            # Also clean up java class files if applicable
            if language == "java" and 'class_name' in locals() and class_name:
                class_file = f"{os.path.dirname(temp_filename)}/{class_name}.class"
                if os.path.exists(class_file):
                    os.unlink(class_file)
            # Clean up C++ compiled executable
            if (language == "cpp" or language == "c++") and 'compiled_file' in locals():
                if os.path.exists(compiled_file):
                    os.unlink(compiled_file)
        except:
            pass
    
    return result
def get_language_from_domain(domain):
    """
    Map a domain to an appropriate programming language for code execution
    """
    domain_language_map = {
        "Python": "python",
        "Java": "java",
        "C++": "cpp",
        "JavaScript": "javascript",
        "React": "javascript",
        "Node.js": "javascript",
        "Full Stack": "javascript",  # Default to JavaScript for full stack
        "Data Science": "python",
        "Machine Learning": "python",
        "DevOps": "python",  # Default to Python for DevOps
        "Cloud Computing": "python",  # Default to Python for Cloud
        "Database": "sql",  # SQL might need special handling
        "System Design": "pseudocode",  # Not executable
        "Algorithms": "python"  # Default to Python for algorithms
    }
    
    return domain_language_map.get(domain, "python")  # Default to Python if domain not found


# ========== UPDATES TO SESSION STATE ==========
# Add these keys to your default_state dictionary:
#
# "is_coding_question": False,
# "code_submission": "",
# "code_language": "python",
# "code_result": None,
# "code_feedback": "",
# "supported_languages": ["python"]  # Add more as you implement them

def extract_score(feedback):
    for line in feedback.splitlines():
        if line.lower().startswith("score:"):
            try:
                score_text = line.split(":")[1].strip()
                # Handle cases like "Score: 7/10" or just "Score: 7"
                score_text = score_text.split("/")[0].strip()
                return int(score_text)
            except:
                pass
    
    # Fallback: look for any number between 0 and 10
    for line in feedback.splitlines():
        for token in line.split():
            if token.isdigit() and 0 <= int(token) <= 10:
                return int(token)
    return 5  # Default score if extraction fails

def reset_interview():
    for key in default_state:
        st.session_state[key] = default_state[key]

def get_domain_icon(domain):
    icons = {
        "Python": "🐍",
        "Java": "☕",
        "C++": "⚙",
        "Full Stack": "🌐",
        "Data Science": "📊",
        "DevOps": "🔄",
        "Machine Learning": "🤖",
        "Cloud Computing": "☁",
        "JavaScript": "📱",
        "React": "⚛",
        "Node.js": "📦",
        "Database": "🗄",
        "System Design": "🏗",
        "Algorithms": "🧮"
    }
    return icons.get(domain, "💻")

def create_score_chart():
    if not st.session_state.scores:
        return None
    
    fig, ax = plt.subplots(figsize=(4, 4))
    scores = st.session_state.scores
    avg_score = sum(scores) / len(scores)
    
    # Create a donut chart
    ax.pie([avg_score, 10-avg_score], 
           colors=['#3B82F6', '#E5E7EB'],
           wedgeprops=dict(width=0.4, edgecolor='w'),
           startangle=90)
    
    # Add text in center
    ax.text(0, 0, f"{avg_score:.1f}", ha='center', va='center', fontsize=24, fontweight='bold')
    ax.text(0, -0.2, "Average", ha='center', va='center', fontsize=12)
    
    # Remove axes
    ax.axis('equal')
    plt.axis('off')
    
    return fig

def get_reward_badge(score_percentage):
    if score_percentage >= 90:
        return "🏆", "Expert Interviewer", "Congratulations on your exceptional performance! You've demonstrated expert-level knowledge."
    elif score_percentage >= 80:
        return "🥇", "Advanced Proficiency", "Excellent work! You've shown strong technical knowledge and communication skills."
    elif score_percentage >= 70:
        return "🥈", "Strong Performer", "Great job! You've demonstrated solid understanding of technical concepts."
    elif score_percentage >= 60:
        return "🥉", "Competent Technologist", "Good effort! You've shown competence in technical areas."
    elif score_percentage >= 50:
        return "🎖", "Promising Talent", "Decent work! You're on the right track with your technical knowledge."
    else:
        return "", "Better Luck Next Time", "You've taken the first steps. Keep learning and practicing!"


def get_certificate_html(username, domain, num_questions, avg_score):
    date_str = datetime.now().strftime("%B %d, %Y")
    
    # Debug: Check if username is empty
    display_name = username if username and username.strip() else "deeraj"
    
    certificate = f"""
    <div class="certificate">
        <div class="certificate-title">Certificate of Achievement</div>
        <div class="certificate-text">This is to certify that</div>
        <div class="certificate-name">{display_name}</div>
        <div class="certificate-text">has successfully completed a technical interview assessment in <strong>{domain}</strong>, 
        answering {num_questions} questions with an average score of <strong>{avg_score:.1f}/10</strong></div>
        <div class="certificate-seal">🏅</div>
        <div class="certificate-date">Issued on {date_str}</div>
    </div>
    """
    return certificate

def generate_certificate_image(username, domain, num_questions, avg_score):
    """
    Generate a certificate as a PIL Image
    """
    # Create a white image with appropriate dimensions
    width, height = 800, 600
    certificate = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(certificate)
    
    # Debug: Check if username is empty and provide fallback
    display_name = username if username and username.strip() else "deeraj"
    
    # Try to load fonts - fallback to default if not available
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        name_font = ImageFont.truetype("arial.ttf", 42)
        text_font = ImageFont.truetype("arial.ttf", 28)
        seal_font = ImageFont.truetype("arial.ttf", 96)

    except IOError:
        # Fallback to default font
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        seal_font = ImageFont.load_default()
    
    # Draw certificate border
    border_width = 20
    draw.rectangle([(border_width, border_width), (width-border_width, height-border_width)], 
                  outline="#3B82F6", width=5)
    
    # Draw title
    title = "Certificate of Achievement"
    title_width = draw.textlength(title, font=title_font)
    draw.text(((width - title_width) / 2, 60), title, fill="#1E40AF", font=title_font)
    
    # Draw text
    draw.text((width/2, 120), "This is to certify that", fill="#1F2937", font=text_font, anchor="mm")
    
    # Draw name - FIXED LINE
    draw.text((width/2, 180), display_name, fill="#1E3A8A", font=name_font, anchor="mm")
    
    # Draw certificate text
    cert_text = f"has successfully completed a technical interview assessment in {domain}, " \
               f"answering {num_questions} questions with an average score of {avg_score:.1f}/10"
               
    # Wrap text to fit certificate width
    wrapped_text = textwrap.fill(cert_text, width=40)
    lines = wrapped_text.split('\n')
    y_position = 250
    for line in lines:
        draw.text((width/2, y_position), line, fill="#1F2937", font=text_font, anchor="mm")
        y_position += 30
    
    # Draw date
    from datetime import datetime
    date_str = datetime.now().strftime("%B %d, %Y")
    draw.text((width/2, 500), f"Issued on {date_str}", fill="#6B7280", font=text_font, anchor="mm")
    
    # Add "seal" or emoji - simplified approach without the problematic code
    seal_text = "🏅"
    draw.text((width/2, 400), seal_text, fill="#3B82F6", font=seal_font, anchor="mm")
    
    return certificate


def download_certificate():
    """
    Generate and create a download link for the certificate
    """
    if not st.session_state.scores:
        return None
    
    # Get username with fallback
    username = st.session_state.get("username", "").strip()
    if not username:
        username = "deeraj"
    
    domain = st.session_state.domain
    num_questions = len(st.session_state.scores)
    avg_score = sum(st.session_state.scores) / num_questions if num_questions > 0 else 0
    
    # Debug print to check username
    print(f"Certificate generation - Username: '{username}', Domain: {domain}")
    
    # Generate certificate image
    certificate_img = generate_certificate_image(username, domain, num_questions, avg_score)
    
    # Save to BytesIO
    buf = BytesIO()
    certificate_img.save(buf, format="PNG")
    buf.seek(0)
    
    # Encode to base64 for download
    img_str = base64.b64encode(buf.read()).decode()
    
    # Create download link with safe filename
    safe_username = username.replace(" ", "_").replace("/", "_")
    href = f'<a href="data:image/png;base64,{img_str}" download="certificate_{safe_username}.png" class="btn-success" style="text-decoration:none; text-align:center; display:block; padding:10px; margin-top:10px;">Download Certificate</a>'
    
    return href

def fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    return img_str

def create_confetti_html():
    """
    Create confetti elements for the celebration animation
    """
    confetti_html = '<div class="confetti-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden; pointer-events: none;">'
    
    for i in range(30):
        x = random.randint(0, 100)
        y = random.randint(-100, 0)
        delay = random.uniform(0, 5)
        size = random.randint(5, 15)
        color = random.choice(['#FCD34D', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6'])
        
    return confetti_html
        
# 1. Modify the next_question() function

# 3. Update the next_question() function to reset the spoken flag
def next_question(is_coding=False):
    """
    Generate a new question and reset all question-related states
    """
    # Increment question counter
    st.session_state.question_number += 1
    
    # Set coding question flag
    st.session_state.is_coding_question = is_coding
    
    # Set appropriate language based on domain
    if is_coding:
        st.session_state.code_language = get_language_from_domain(st.session_state.domain)
    
    # Generate new question
    try:
        with st.spinner("Generating next question..."):
            # Generate domain-specific question directly
            if is_coding:
                st.session_state.current_question = generate_coding_question(st.session_state.domain)
            else:
                st.session_state.current_question = generate_question(st.session_state.domain)
    except Exception as e:
        st.error(f"Error generating question: {str(e)}")
        if is_coding:
            st.session_state.current_question = f"Write a function in {st.session_state.domain} to solve the following problem: [Problem description would go here]"
        else:
            st.session_state.current_question = f"Tell me about a challenging problem you solved in {st.session_state.domain}."
    
    # Reset all question-related states
    st.session_state.spoken = False
    st.session_state.answered = False
    st.session_state.finished = False
    st.session_state.recording_started = False
    st.session_state.audio_thread = None
    st.session_state.transcript = ""
    st.session_state.feedback = ""
    st.session_state.score = 0
    st.session_state.code_submission = ""
    st.session_state.code_result = None
    st.session_state.code_feedback = ""


