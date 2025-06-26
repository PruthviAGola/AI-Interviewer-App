# === Frontend Streamlit App ===
import streamlit as st 
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from backend import *

# ========== PAGE RENDERING ==========
def render_intro_page():
    st.markdown(get_robot_logo_html(), unsafe_allow_html=True)
    st.markdown("<h1 class='main-header welcome-animation'>AI Technical Interviewer</h1>", unsafe_allow_html=True)
    
    st.markdown("<div class='intro-box'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Prepare for Technical Interviews with AI</h2>", unsafe_allow_html=True)
    st.markdown("<p>Welcome to the AI Technical Interviewer! Practice your technical interview skills with our AI-powered interviewer that asks questions, evaluates your responses, and provides feedback.</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <ul class="feature-list">
        <li>Answer questions verbally and get real-time transcription</li>
        <li>Receive detailed feedback and scoring on your responses</li>
        <li>Practice with questions across various technical domains</li>
        <li>Track your progress and improvement over time</li>
        <li>No time limit - answer at your own pace</li>
    </ul>
    """, unsafe_allow_html=True)
    
    st.markdown("<p>Click the button below to set up your interview session!</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Take Interview", key="start_setup", help="Begin setting up your interview"):
            st.session_state.page = "setup"
            st.rerun()

def render_setup_page():
    st.markdown(get_robot_logo_html(), unsafe_allow_html=True)
    st.markdown("<h1 class='main-header'>Interview Setup</h1>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Customize Your Interview</h2>", unsafe_allow_html=True)
    
    # Add this descriptive text to ensure content is visible
    st.markdown("<p>Please enter your details below to personalize your technical interview experience.</p>", unsafe_allow_html=True)
    
    # Username input
    username = st.text_input("Your Name:", value=st.session_state.username, 
                             placeholder="Enter your name", key="input_username")
    st.session_state.username = username
    
    # Domain selection
    domain_options = ["Python", "Java", "C++", "JavaScript", "React", "Node.js", 
                     "Full Stack", "Data Science", "Machine Learning", "DevOps", 
                     "Cloud Computing", "Database", "System Design", "Algorithms"]
    
    domain = st.selectbox("Technical Domain:", domain_options, 
                         index=domain_options.index(st.session_state.domain) if st.session_state.domain in domain_options else 0,
                         help="Select the technical domain for your interview questions")
    st.session_state.domain = domain
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        start_disabled = not st.session_state.username.strip()
        if st.button("Start Interview", disabled=start_disabled, key="start_interview", 
                   help="Begin your technical interview"):
            reset_interview()
            st.session_state.page = "interview"
            st.session_state.interview_started = True
            # Initialize with first domain-specific question
            st.session_state.question_number = 1  # Start at 1 instead of 0
            st.session_state.current_question = ""  # This will trigger generation in render_interview_page
            st.rerun()

# Also need to modify the interview page rendering to generate a question if none exists

def render_interview_page():
    # Header
    domain_icon = get_domain_icon(st.session_state.domain)
    st.markdown(f"<h1 class='main-header'>{domain_icon} {st.session_state.domain} Technical Interview</h1>", unsafe_allow_html=True)
    
    # Question Card
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    # Generate first question if none exists
    if not st.session_state.current_question:
        # For the first question, randomly decide if it's a coding question based on the domain
        is_coding_first = random.choice([True, False])
        
        # Generate domain-specific question directly
        try:
            with st.spinner("Generating question..."):
                if is_coding_first:
                    st.session_state.current_question = generate_coding_question(st.session_state.domain)
                    st.session_state.is_coding_question = True
                else:
                    st.session_state.current_question = generate_question(st.session_state.domain)
                    st.session_state.is_coding_question = False
        except Exception as e:
            st.error(f"Error generating question: {str(e)}")
            st.session_state.current_question = f"Explain a key concept in {st.session_state.domain}."
            st.session_state.is_coding_question = False
    
    # Set appropriate question title based on question number and type
    if st.session_state.is_coding_question:
        question_title = f"Coding Question {st.session_state.question_number}"
    else:
        question_title = f"Question {st.session_state.question_number}"
    st.markdown(f"""
    <div class='question-card'>
        <h3>{question_title}</h3>
        <p>{st.session_state.current_question}</p>
    </div>
    """, unsafe_allow_html=True)

    
    # Replace the existing speak button with your new one
    # Replace the existing speak button with your new one
    if not st.session_state.is_coding_question:
       col1, col2 = st.columns([1, 1])
       with col1:
          if st.button("🔊 Speak Question Aloud", key="speak_button", on_click=on_speak_button_click): 
              pass
       with col2:
           if st.button("⏹ Stop Speak", key="stop_speak_button", on_click=on_stop_speak_button_click): 
               pass

    
    # Speak the question if not already spoken and it's not a coding question
    if not st.session_state.spoken and not st.session_state.is_coding_question:
        with st.spinner("Speaking question..."):
            speak_question()
    
    # The rest of the function remains the same...
    # Different interfaces for coding vs. speaking questions
    if st.session_state.is_coding_question:
        # Coding interface
        if not st.session_state.answered:
            # Code editor
            code_submission = st.text_area("Your Code Solution:", 
                                         value=st.session_state.code_submission,
                                         height=300,
                                         key="code_editor")
            st.session_state.code_submission = code_submission
            
            # Run and Submit buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Run Code", key="run_code"):
                    if not st.session_state.code_submission.strip():
                        st.warning("Please enter code before running.")
                    else:
                        with st.spinner("Running your code..."):
                            result = run_code(st.session_state.code_submission, st.session_state.code_language)
                            st.session_state.code_result = result
            
            with col2:
                if st.button("Submit Solution", key="submit_code"):
                    if not st.session_state.code_submission.strip():
                        st.warning("Please enter code before submitting.")
                    else:
                        with st.spinner("Evaluating your solution..."):
                            feedback = evaluate_code_submission(
                                st.session_state.current_question,
                                st.session_state.code_submission,
                                st.session_state.code_language
                            )
                            score = extract_score(feedback)
                            
                            st.session_state.code_feedback = feedback
                            st.session_state.feedback = feedback
                            st.session_state.score = score
                            st.session_state.scores.append(score)
                            st.session_state.total_score += score
                            st.session_state.questions_asked += 1
                            st.session_state.answered = True
                            st.session_state.finished = True
                            
                            # Save logs
                            with open(f"transcripts/q{st.session_state.question_number}_code.txt", "w") as f:
                                f.write(f"Q: {st.session_state.current_question}\nA: {st.session_state.code_submission}")
                            with open(f"feedback/q{st.session_state.question_number}_feedback.txt", "w") as f:
                                f.write(feedback)
                            
                            st.rerun()
            
            # Show code execution results if available
            if st.session_state.code_result:
                st.markdown("<div class='feedback-card'>", unsafe_allow_html=True)
                st.markdown("<h3>Code Execution Result:</h3>", unsafe_allow_html=True)
                
                if st.session_state.code_result["success"]:
                    st.code(st.session_state.code_result["output"], language="text")
                else:
                    st.error("Error:")
                    st.code(st.session_state.code_result["error"], language="text")
                
                st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        # Theory question interface - Now with text area option
        if not st.session_state.answered:
            # Add text area for typing answers
            text_answer = st.text_area("Type your answer here:", 
                                      height=200,
                                      key="text_answer",
                                      help="Type your answer or use voice recording below")
            
            # Submit text answer button
            if st.button("Submit Answer", key="submit_text_answer"):
                if not text_answer.strip():
                    st.warning("Please type an answer before submitting.")
                else:
                    with st.spinner("Evaluating your answer..."):
                        # Store the text answer in transcript field
                        st.session_state.transcript = text_answer
                        
                        # Evaluate the answer
                        feedback = evaluate_answer(st.session_state.current_question, text_answer)
                        score = extract_score(feedback)
                        
                        # Update session state
                        st.session_state.feedback = feedback
                        st.session_state.score = score
                        st.session_state.scores.append(score)
                        st.session_state.total_score += score
                        st.session_state.questions_asked += 1
                        st.session_state.answered = True
                        st.session_state.finished = True
                        
                        # Save logs
                        with open(f"transcripts/q{st.session_state.question_number + 1}.txt", "w") as f:
                            f.write(f"Q: {st.session_state.current_question}\nA: {text_answer}")
                        with open(f"feedback/q{st.session_state.question_number + 1}_feedback.txt", "w") as f:
                            f.write(feedback)
                        with open("logs/session_log.txt", "a") as log:
                            avg_score = sum(st.session_state.scores) / len(st.session_state.scores)
                            session_id = uuid.uuid4()
                            log.write(f"Session ID: {session_id} | User: {st.session_state.username} | "
                                    f"Domain: {st.session_state.domain} | "
                                    f"Q{st.session_state.question_number + 1} Score: {score} | Avg: {avg_score:.2f}\n")
                        
                        st.rerun()
            
            # Add separator between text and voice options
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            st.markdown("<p><em>Or record your answer using voice:</em></p>", unsafe_allow_html=True)
            
            # Original voice recording controls
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if not st.session_state.recording_started:
                    if st.button("🎙 Start Recording", key="start_rec", help="Begin recording your answer"):
                        start_recording()
                        st.rerun()
            
            with col2:
                if st.session_state.recording_started:
                    if st.button("⏹ Stop Recording", key="stop_rec", help="Stop recording and evaluate answer"):
                        stop_recording()
                        st.rerun()
    
    # Question navigation buttons
    if st.session_state.answered:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("➡ Next Question", key="next_regular_q", help="Proceed to the next regular question"):
                next_question(is_coding=False)
                st.rerun()
        
        with col2:
            if st.button("💻 Next Coding Question", key="next_coding_q", help="Proceed to the next coding question"):
                next_question(is_coding=True)
                st.rerun()
        
        with col3:
            # Allow ending interview if any questions have been answered
            if st.session_state.questions_asked > 0:
                if st.button("🏁 End Interview", key="end_interview", help="Finish interview and see results"):
                    st.session_state.page = "result"
                    st.session_state.interview_ended = True
                    st.rerun()
    else:
        # Only show the End Interview button if not in the middle of a question
        if not st.session_state.recording_started and st.session_state.questions_asked > 0:
            if st.button("🏁 End Interview", key="end_interview_early", help="Finish interview and see results"):
                st.session_state.page = "result"
                st.session_state.interview_ended = True
                st.rerun()
        
    # Show recording indicator and timer if currently recording
    if st.session_state.recording_started:
        elapsed_time = int(time.time() - st.session_state.recording_start_time)
        minutes, seconds = divmod(elapsed_time, 60)
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-top: 10px;">
            <span class="recording-pulse"></span>
            <span>Recording: {minutes:02d}:{seconds:02d}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Show transcript if available
    if st.session_state.transcript:
        st.markdown("<div class='feedback-card'>", unsafe_allow_html=True)
        st.markdown("<h3>Your Response:</h3>", unsafe_allow_html=True)
        st.markdown(f"<p>{st.session_state.transcript}</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Show feedback if available
    if st.session_state.feedback:
        st.markdown("<div class='feedback-card'>", unsafe_allow_html=True)
        st.markdown("<h3>Feedback:</h3>", unsafe_allow_html=True)
        
        # Process the feedback for better rendering
        feedback_parts = st.session_state.feedback.splitlines()
        for part in feedback_parts:
            if part.lower().startswith("score:"):
                score_value = part.split(":")[1].strip()
                st.markdown(f"<p><strong>{part}</strong></p>", unsafe_allow_html=True)
            elif part.startswith("Strengths:") or part.startswith("Areas for Improvement:") or part.startswith("Overall Feedback:") or part.startswith("Correctness:") or part.startswith("Code Quality:") or part.startswith("Solution Approach:"):
                st.markdown(f"<p><strong>{part}</strong></p>", unsafe_allow_html=True)
            elif part.startswith("-"):
                st.markdown(f"<p style='margin-left: 20px;'>{part}</p>", unsafe_allow_html=True)
            elif part.strip():
                st.markdown(f"<p>{part}</p>", unsafe_allow_html=True)
                
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
def render_result_page():
    st.markdown(get_robot_logo_html(), unsafe_allow_html=True)
    st.markdown("<h1 class='main-header'>Interview Results</h1>", unsafe_allow_html=True)
    
    if not st.session_state.scores:
        st.warning("No questions were answered. Please complete at least one question.")
        if st.button("Back to Start"):
            reset_interview()
            st.rerun()
        return
    
    # Calculate total score
    total_questions = len(st.session_state.scores)
    avg_score = sum(st.session_state.scores) / total_questions
    score_percentage = (avg_score / 10) * 100
    
    # Get reward based on score
    badge_icon, badge_title, badge_description = get_reward_badge(score_percentage)
    
    # Reward card with animation - but only if we have a badge icon
    if badge_icon:
        st.markdown(f"""
        <div class="reward-card" style="position: relative;">
            {create_confetti_html()}
            <span class="reward-badge">{badge_icon}</span>
            <h2 class="reward-title">{badge_title}</h2>
            <p>{badge_description}</p>
            <p>Questions Answered: {total_questions} | Average Score: {avg_score:.1f}/10</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Alternative version without badge icon
        st.markdown(f"""
        <div class="reward-card" style="position: relative;">
            {create_confetti_html()}
            <h2 class="reward-title">{badge_title}</h2>
            <p>{badge_description}</p>
            <p>Questions Answered: {total_questions} | Average Score: {avg_score:.1f}/10</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Score breakdown
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-header'>Score Breakdown</h2>", unsafe_allow_html=True)
    
    # Display chart
    fig = create_score_chart()
    if fig:
        st.pyplot(fig)
    
    # Question-by-question scores
    for i, score in enumerate(st.session_state.scores):
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="flex: 1;">Question {i+1}</div>
            <div style="flex: 2;">
                <div style="background-color: #E5E7EB; border-radius: 4px; height: 8px; width: 100%;">
                    <div style="background-color: #3B82F6; border-radius: 4px; height: 8px; width: {score*10}%;"></div>
                </div>
            </div>
            <div style="flex: 0 0 30px; text-align: right;">{score}/10</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Certificate
    username = st.session_state.get("username", "").strip()
    if not username:
        username = "deeraj"
        st.session_state.username = username
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h2 class='sub-header'>Your Certificate</h2>", unsafe_allow_html=True)
        
        certificate_html = get_certificate_html(
            st.session_state.username, 
            st.session_state.domain,
            total_questions,
            avg_score
        )
        

        certificate_css = """
        <style>
           .certificate {
                 background: linear-gradient(135deg, #fff, #f9f9f9);
               border: 15px solid #3B82F6;
               border-radius: 15px;
               padding: 3rem;
               position: relative;
               box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
               text-align: center;
               max-width: 800px;
               margin: 0 auto;
           }
           .certificate-title {
               font-size: 2.5rem;
               color: #1E40AF;
               margin-bottom: 1.5rem;
               font-family: 'Times New Roman', serif;
           }
           .certificate-name {
               font-size: 2rem;
               font-weight: bold;
               color: #1E3A8A;
               margin-bottom: 2rem;
               text-decoration: underline;
           }
           .certificate-text {
               font-size: 1.2rem;
               margin-bottom: 2rem;
               color: #1F2937;
           }
           .certificate-seal {
               display: inline-block;
               font-size: 4rem;
               margin: 1rem;
               color: #3B82F6;
           }
           .certificate-date {
               font-size: 1rem;
               color: #6B7280;
               margin-top: 3rem;
           }
        </style>
           """
        st.markdown(certificate_css, unsafe_allow_html=True)
        st.markdown(certificate_html, unsafe_allow_html=True)

        
        
        download_link = download_certificate()
        if download_link:
            st.markdown(download_link, unsafe_allow_html=True)
        
            st.markdown("</div>", unsafe_allow_html=True)
        
     # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start New Interview", key="new_interview"):
            reset_interview()
            st.session_state.page = "setup"
            st.rerun()
    
    with col2:
        if st.button("Back to Home", key="back_home"):
            reset_interview()
            st.rerun()

# ========== MAIN APP FLOW ==========
def main():
    # Store logs for analytics
    log_file = "logs/app_usage.txt"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as log:
        log.write(f"{datetime.now()} - App accessed\n")
    
    # Create folders for transcripts and feedback if they don't exist
    os.makedirs("transcripts", exist_ok=True)
    os.makedirs("feedback", exist_ok=True)
    
    # Render appropriate page based on app state
    if st.session_state.page == "intro":
        render_intro_page()
    elif st.session_state.page == "setup":
        render_setup_page()
    elif st.session_state.page == "interview":
        render_interview_page()
    elif st.session_state.page == "result":
        render_result_page()
if __name__ == "__main__":
    local_css("style.css")
    main()