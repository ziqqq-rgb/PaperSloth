import os

# Fix for Apple Silicon (Mac) math processing limitations
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

from transformers import AutoTokenizer
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
from docling.chunking import HybridChunker
from llama_index.core.schema import TextNode
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# --- Configuration ---
FILE_PATH = "/Users/raziqs/Desktop/PaperSloth/PaperSloth/rag pipeline/test1.pdf"
EMBED_MODEL_ID = "nomic-ai/nomic-embed-text-v2-moe"

def build_ingestion_pipeline():
    # 1. Setup the Tokenizer for accurate chunk limits
    print("1. Loading Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_ID, local_files_only=False)

    # 2. Configure Docling Pipeline (Merging your OCR snippet!)
    print("2. Configuring Docling OCR and Layout Parser...")
    pipeline_options = PdfPipelineOptions()
    
    # Enable OCR for scanned PDFs (Falls back to EasyOCR/Tesseract)
    pipeline_options.do_ocr = True 
    
    # Enable image extraction for your multi-modal Vision LLM later
    pipeline_options.generate_picture_images = True 
    
    # Force CPU processing to prevent Mac GPU crashing on heavy OCR tasks
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, 
        device=AcceleratorDevice.CPU 
    )

    # Register the pipeline options
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    # 3. Parse PDF
    print(f"3. Parsing PDF (this may take longer due to OCR): {FILE_PATH}...")
    parsed_doc = converter.convert(FILE_PATH).document

    # 4. Hybrid Chunking
    print("4. Executing Token-Aware Hybrid Chunking...")
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=512,
        merge_peers=True
    )
    docling_chunks = list(chunker.chunk(parsed_doc))

    # 5. Bridge to LlamaIndex
    print("5. Converting to LlamaIndex Nodes...")
    llama_nodes = []
    
    for i, chunk in enumerate(docling_chunks):
        node = TextNode(
            text=chunk.text,
            metadata={
                "source_file": FILE_PATH,
                "chunk_index": i,
                "has_ocr": True # Just a flag to remember this pipeline used OCR
            }
        )
        llama_nodes.append(node)

    print(f"✅ Success! Created {len(llama_nodes)} LlamaIndex Nodes.")
    return llama_nodes


# --- LlamaIndex Execution ---
if __name__ == "__main__":
    # Point LlamaIndex to your local Ollama models
    Settings.llm = Ollama(model="gemma3:1b", request_timeout=300.0)
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text-v2-moe")

    # Run the pipeline
    nodes = build_ingestion_pipeline()

    if nodes:
        print("6. Building Vector Store Index...")
        index = VectorStoreIndex(nodes)
        
        print("\n--- Testing Retrieval ---")
        query_engine = index.as_query_engine()
        response = query_engine.query("What are the questions asked in this paper?")
        print(response)