import fitz
import json
import os


def extract_text_from_pdf(pdf_path):
    """Extract raw text from any PDF"""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num, page in enumerate(doc):
        full_text += f"\n--- Page {page_num + 1} ---\n"
        full_text += page.get_text()
    doc.close()
    return full_text


def extract_images_from_pdf(pdf_path, output_folder):
    """Extract images from PDF — needed for stamps and signatures"""
    doc = fitz.open(pdf_path)
    os.makedirs(output_folder, exist_ok=True)
    image_paths = []

    for page_num, page in enumerate(doc):
        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_path = f"{output_folder}/page{page_num+1}_img{img_index}.{image_ext}"
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            image_paths.append(image_path)

    doc.close()
    return image_paths


def extract_document(pdf_path):
    """Main extraction function — returns everything"""
    result = {
        "file": pdf_path,
        "text": extract_text_from_pdf(pdf_path),
        "page_count": 0,
        "has_images": False
    }

    doc = fitz.open(pdf_path)
    result["page_count"] = len(doc)
    doc.close()

    return result


# test it directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        result = extract_document(pdf_path)
        print(f"Pages: {result['page_count']}")
        print(f"Text preview:\n{result['text'][:500]}")
    else:
        print("Usage: python extract.py path/to/document.pdf")
