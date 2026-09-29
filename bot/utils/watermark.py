import io
import fitz  # PyMuPDF

def apply_watermark(pdf_bytes: bytes, watermark_text: str) -> bytes:
    try:
        # Load the PDF from memory
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page in doc:
            rect = page.rect
            # Diagonal text from bottom-left to top-right approx
            page.insert_text(
                fitz.Point(50, rect.height - 100),
                watermark_text,
                fontsize=45,
                color=(0, 0, 0),  # Black
                fill_opacity=0.6, # More visible
                rotate=-45,
            )
        
        # Save to memory
        out_bytes = doc.write()
        doc.close()
        return out_bytes
    except Exception as e:
        # If it fails (e.g., not a valid PDF), return original
        print(f"Watermark error: {e}")
        return pdf_bytes
