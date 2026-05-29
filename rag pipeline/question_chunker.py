import re

def parse_docling_output(docling_markdown_text, course_code="RBB3013"):
    lines = docling_markdown_text.split('\n')
    chunks = []
    current_chunk_text = []
    current_q_number = None

    # Headers we must ignore so they don't break the flow
    skip_texts = [
        "Universiti Teknologi PETRONAS", 
        "SULIT", 
        "FINAL EXAMINATION",
        course_code
    ]

    # Regex to detect a question number. 
    # This handles "1.", "1. ", "* 1.", "Q1.", and "Question 1"
    question_pattern = re.compile(r'^(?:\*|#)?\s*(?:Q|Question\s)?\s*(\d+)\s*\.$', re.IGNORECASE)

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # 1. SKIP PDF HEADERS
        if any(skip_text in clean_line for skip_text in skip_texts if skip_text):
            continue

        # 2. DETECT NEW QUESTION
        match = question_pattern.match(clean_line)
        if match:
            # Save the PREVIOUS question chunk before starting the new one
            if current_q_number is not None:
                chunks.append({
                    "question_number": current_q_number,
                    "text": "\n".join(current_chunk_text)
                })
            
            # Start tracking the NEW question
            current_q_number = match.group(1) # Extracts just the digit (e.g., "1")
            current_chunk_text = [clean_line] # Add the "1." to the text buffer
            continue 

        # 3. APPEND TEXT TO CURRENT QUESTION
        if current_q_number is not None:
            current_chunk_text.append(clean_line)

    # Don't forget to save the final question (Q5) when the loop finishes!
    if current_q_number is not None and current_chunk_text:
        chunks.append({
            "question_number": current_q_number,
            "text": "\n".join(current_chunk_text)
        })

    return chunks