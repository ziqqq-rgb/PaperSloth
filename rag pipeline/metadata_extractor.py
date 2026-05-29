from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from pypdf import PdfReader # pip install pypdf

# 1. Define the exact JSON structure we want Ollama to return
class ExamMetadata(BaseModel):
    course_code: str = Field(description="The subject code, e.g., RBB3013")
    course_name: str = Field(description="The name of the subject, e.g., INSTRUMENTATION AND CONTROL")
    semester_type: str = Field(description="The semester intake month or term, e.g., SEPTEMBER or MAY")
    year: int = Field(description="The 4-digit year of the exam, e.g., 2025")

def get_metadata_from_pdf(pdf_path: str) -> dict:
    """Reads ONLY the first page of a PDF and uses Ollama to extract structured metadata."""
    
    # Fast extraction of just the cover page (No need to load Docling for this)
    try:
        reader = PdfReader(pdf_path)
        cover_text = reader.pages[0].extract_text()
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return None

    # Connect to your local Ollama model (e.g., llama3.2 or qwen)
    llm = ChatOllama(model="gemma3:1b", temperature=0)
    
    # Force the LLM to reply strictly in our Pydantic JSON format
    structured_llm = llm.with_structured_output(ExamMetadata)
    
    prompt = (
        f"You are a helpful data extraction assistant. Extract the course code, "
        f"course name, semester type either 'SEPTEMBER' or 'MAY' or 'JANUARY', and year from this exam cover page.\n\n"
        f"COVER PAGE TEXT:\n{cover_text}"
    )
    
    # Execute the local LLM call
    result = structured_llm.invoke(prompt)
    
    return result.model_dump() # Returns a clean Python dictionary

# --- Quick Test (You can run this file directly to test it) ---
if __name__ == "__main__":
    test_pdf = "rag pipeline/test1.pdf"
    metadata = get_metadata_from_pdf(test_pdf)
    print("Extracted Metadata:", metadata)