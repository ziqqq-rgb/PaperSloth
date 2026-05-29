import re

def parse_docling_output(docling_markdown_text, course_code=""):
    lines = docling_markdown_text.split('\n')
    chunks = []
    current_chunk_text = []
    current_q_number = None

    # Common UTP headers we want to completely ignore
    skip_texts = [
        "Universiti Teknologi PETRONAS", 
        "SULIT", 
        "FINAL EXAMINATION",
        course_code # We dynamically ignore the course code (e.g., "RBB3013")
    ]

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # 1. SKIP HEADERS
        if any(skip_text in clean_line for skip_text in skip_texts if skip_text):
            continue

        # 2. DETECT NEW QUESTION (Matches strictly "1.", "2.", "10.")
        if re.match(r'^(\d+)\.$', clean_line):
            # If we were already tracking a question, save it before starting the new one
            if current_q_number is not None:
                chunks.append({
                    "question_number": current_q_number,
                    "text": "\n".join(current_chunk_text)
                })
            
            # Start tracking the new question
            current_q_number = clean_line[:-1] # Removes the dot, keeping just the number
            current_chunk_text = [] # Reset text buffer
            continue # Move to next line

        # 3. APPEND TEXT TO CURRENT QUESTION
        if current_q_number is not None:
            current_chunk_text.append(clean_line)

    # Don't forget to save the very last question when the loop ends!
    if current_q_number is not None and current_chunk_text:
        chunks.append({
            "question_number": current_q_number,
            "text": "\n".join(current_chunk_text)
        })

    return chunks