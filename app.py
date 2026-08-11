import streamlit as st
import fitz  # PyMuPDF
import io

# --- מילון המרה מאותיות בעברית לאנגלית ---
hebrew_to_english = {
    'א': 'A', 'ב': 'B', 'ג': 'C', 'ד': 'D', 'ה': 'E', 'ו': 'F',
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.'
}

def process_pdf(pdf_bytes, remove_markers, shrink_letters):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    for page in doc:
        # --- 1. מחיקת מרקרים צהובים (צורות וקטוריות) ---
        if remove_markers:
            for xref in page.get_contents():
                stream = doc.xref_stream(xref)
                if stream:
                    stream_str = stream.decode("latin1")
                    # החלפת צהוב בלבן
                    stream_str = stream_str.replace("1 1 0 rg", "1 1 1 rg")
                    stream_str = stream_str.replace("1 1 0 RG", "1 1 1 RG")
                    stream_str = stream_str.replace("1.0 1.0 0.0 rg", "1.0 1.0 1.0 rg")
                    stream_str = stream_str.replace("1.0 1.0 0.0 RG", "1.0 1.0 1.0 RG")
                    doc.update_stream(xref, stream_str.encode("latin1"))
                    
        # --- 2. החלפת אותיות מוגדלות לאנגלית (A-E) ---
        if shrink_letters:
            dict_data = page.get_text("dict")
            for block in dict_data["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            # בדיקה האם גודל הגופן חריג (גדול מ-18)
                            if span["size"] > 18:
                                # הרחבת הריבוע הלבן כדי למחוק שאריות של האות המקורית
                                rect = fitz.Rect(span["bbox"])
                                rect = rect + (-2, -2, 2, 2) 
                                
                                original_text = span["text"].strip()
                                origin = span["origin"] # נקודת העיגון של האות
                                
                                if original_text:
                                    # ציור המלבן הלבן להסתרת האות בעברית
                                    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                    
                                    # המרה לאנגלית בעזרת המילון
                                    # שימוש בפונקציית get - אם התו לא במילון, הוא ישאיר אותו כמו שהוא
                                    new_text = hebrew_to_english.get(original_text, original_text)
                                    
                                    # למקרה שיש רווחים נסתרים בתוך הטקסט
                                    if new_text == original_text:
                                        clean_text = original_text.replace(" ", "")
                                        new_text = hebrew_to_english.get(clean_text, clean_text)
                                    
                                    # כתיבת האות החדשה באנגלית, בגודל נורמלי
                                    page.insert_text(origin, new_text, fontsize=12, color=(0, 0, 0))
                                    
    output_pdf = io.BytesIO()
    doc.save(output_pdf)
    doc.close()
    
    return output_pdf.getvalue()

# --- עיצוב ממשק המשתמש של האפליקציה (Streamlit) ---
st.title("מנקה המבחנים האולטימטיבי 📄✨")
st.write("העלה קובץ PDF ובחר אילו פעולות תרצה לבצע עליו כדי להכין אותו לתרגול.")

# אפשרויות בחירה למשתמש (Checkboxes)
remove_markers_cb = st.checkbox("מחק מרקרים צהובים", value=True)
shrink_letters_cb = st.checkbox("החלף אותיות תשובה מוגדלות (א, ב, ג...) ל-(A, B, C...)", value=True)

# כפתור העלאת קובץ
uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    # כפתור התחלת פעולה
    if st.button("נקה את המבחן"):
        with st.spinner("מעבד את הקובץ..."):
            
            # קריאה לפונקציה המשולבת שלנו
            cleaned_pdf_bytes = process_pdf(uploaded_file.read(), remove_markers_cb, shrink_letters_cb)
            
            st.success("הקובץ נוקה בהצלחה!")
            
            # כפתור הורדת הקובץ הנקי
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"clean_{uploaded_file.name}",
                mime="application/pdf"
            )
