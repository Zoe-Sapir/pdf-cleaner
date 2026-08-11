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
                    
        # --- 2. המרת כל אותיות התשובה לאנגלית (וגם הקטנה של המוגדלות) ---
        if shrink_letters:
            dict_data = page.get_text("dict")
            for block in dict_data["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            original_text = span["text"].strip()
                            clean_text = original_text.replace(" ", "") # ניקוי רווחים נסתרים
                            
                            # בדיקה האם רסיס הטקסט הוא אחת מאותיות התשובה במילון שלנו
                            if clean_text in hebrew_to_english:
                                
                                # שימוש בגבולות המדויקים של האות בלבד, בלי שוליים שדורסים טקסט!
                                rect = fitz.Rect(span["bbox"])
                                origin = span["origin"]
                                
                                # ציור המלבן הלבן המדויק להסתרת האות בעברית (גדולה או קטנה)
                                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                
                                # המרה לאנגלית בעזרת המילון
                                new_text = hebrew_to_english[clean_text]
                                
                                # כתיבת האות החדשה באנגלית, תמיד בגודל נורמלי ואחיד
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
shrink_letters_cb = st.checkbox("החלף את כל אותיות התשובה (א, ב, ג...) לאנגלית (A, B, C...) ויישר את גודלן", value=True)

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
