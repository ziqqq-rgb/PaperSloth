import os
from metadata_extractor import get_metadata_from_pdf
from question_chunker import parse_docling_output

# --- Docling Imports ---
from langchain_docling import DoclingLoader
from docling.chunking import HybridChunker
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
from docling.document_converter import DocumentConverter, PdfFormatOption

from dotenv import load_dotenv
load_dotenv() 

def build_docling_converter():
    pipeline_options = PdfPipelineOptions()
    pipeline_options.allow_external_plugins = True 
    pipeline_options.generate_picture_images = True # Required for your Vision model later!
    pipeline_options.do_ocr = True 
    
    # Use your Mac's CPU or MPS
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU)
    
    return DocumentConverter(
        format_options={ "pdf": PdfFormatOption(pipeline_options=pipeline_options) }
    )

def ingest_paper(pdf_path):
    print(f"--- Processing: {pdf_path} ---")
    
    # 1. AI METADATA EXTRACTION (The Brain)
    print("1. Extracting Metadata via Ollama...")
    paper_metadata = get_metadata_from_pdf(pdf_path)
    
    if not paper_metadata:
        print("Failed to extract metadata. Skipping.")
        return
    print(f"   -> Found: {paper_metadata['course_code']} ({paper_metadata['semester_type']} {paper_metadata['year']})")

    # 2. DOCLING PDF PARSING (The Muscle)
    print("2. Parsing layout and tables via Docling...")
    custom_converter = build_docling_converter()
    loader = DoclingLoader(file_path=pdf_path, converter=custom_converter)
    raw_docs = loader.load() # This contains the massive markdown string
    
    # Extract the raw markdown text from the Docling output
    full_markdown_text = "\n".join([doc.page_content for doc in raw_docs])

    # 3. QUESTION CHUNKING (The Scalpel)
    print("3. Chunking by Question Number...")
    # Pass the course code so the chunker knows to ignore "RBB3013" if it sees it on page 4
    question_chunks = parse_docling_output(full_markdown_text, course_code=paper_metadata['course_code'])
    print(f"   -> Successfully created {len(question_chunks)} distinct question chunks.")

    # 4. METADATA INJECTION (The Stitch)
    print("4. Attaching global metadata to chunks...")
    final_database_payload = []
    
    for chunk in question_chunks:
        # We merge the global paper metadata with the specific question metadata
        enriched_chunk = {
            "page_content": chunk["text"],
            "metadata": {
                "course_code": paper_metadata["course_code"],
                "course_name": paper_metadata["course_name"],
                "semester": paper_metadata["semester_type"],
                "year": paper_metadata["year"],
                "question_number": chunk["question_number"]
            }
        }
        final_database_payload.append(enriched_chunk)
    
    print("✅ Ingestion prep complete! Ready to embed into Pinecone/Postgres.\n")
    return final_database_payload


# --- TEST IT ON YOUR PDF ---
if __name__ == "__main__":
    pdf_file = "rag pipeline/test1.pdf" # Replace with your actual file path
    final_data = ingest_paper(pdf_file)
    
    # Print out Chunk 1 just to prove it works perfectly
    if final_data:
        print("INSPECTING CHUNK 1:")
        print(f"Metadata: {final_data[0]['metadata']}")
        print(f"Text Preview: {final_data[0]['page_content'][:200]}...")