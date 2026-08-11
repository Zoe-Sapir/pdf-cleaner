import streamlit as st
import fitz  # PyMuPDF
import io
import re

# --- מילון המרה מורחב (כולל נקודות הפוכות וסוגריים) ---
hebrew_to_english = {
    'א': 'A', 'ב': 'B', 'ג': 'C', 'ד': 'D', 'ה': 'E', 'ו': 'F',
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.',
    '.א': '.A', '.ב': '.B', '.ג': '.C', '.ד': '.D', '.ה': '.E', '.ו': '.F',
    'א)': 'A)', 'ב)': 'B)', 'ג)': 'C)', 'ד)': 'D)', 'ה)': 'E)', 'ו)': 'F)',
    '(א)': '(A)', '(ב)': '(B)', '(ג)': '(C)', '(ד)': '(D)', '(ה)': '(E)', '(ו)': '(F)'
}

# --- פונקציה חכמה לזיהוי והעלמת צבעים ---
def clean_color(match):
    c = match.group(0)
    parts = c.split()
    try:
        r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
        op = parts[3]
        
        # אם הצבע הוא שחור מוחלט או לבן מוחלט - לא נוגעים בו
        if (r == 0.0 and g == 0.0 and b == 0.0) or (r == 1.0 and g == 1.0 and b == 1.0):
            return c
            
        # כל צבע אחר (ירוק, צהוב, ורוד, כחול) יוחלף ללבן כדי להעלים אותו
        return f"1 1 1 {op}"
    except:
        return c

def process_pdf(pdf_bytes, remove_markers, shrink_letters, hide_solutions):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    hide_active = False 
    current_y = 0
    
    for page in doc:
        # --- 1. מחיקת כל המסגרות והמרקרים הצבעוניים (שודרג!) ---
        if remove_markers:
            for xref in page.get_contents():
                stream = doc.xref_stream(xref)
                if stream:
                    stream_str = stream.decode("latin1")
                    # מחפש קודי צבע בקובץ ומעביר אותם לפונקציית הניקוי שלנו
                    stream_str = re.sub(r'\b\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+(?:RG|rg)\b', clean_color, stream_str)
                    doc.update_stream(xref, stream_str.encode("latin1"))
                    
        # --- 2. המרת אותיות התשובה לאנגלית ---
        if shrink_letters:
            dict_data = page.get_text("dict")
            for block in dict_data["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            original_text = span["text"].strip()
                            words = original_text.split()
                            replaced = False
                            new_words = []
                            
                            for w in words:
                                if w in hebrew_to_english:
                                    new_words.append(hebrew_to_english[w])
                                    replaced = True
                                else:
                                    new_words.append(w)
                                    
                            if replaced:
                                rect = fitz.Rect(span["bbox"])
                                origin = span["origin"]
                                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                new_text = " ".join(new_words)
                                page.insert_text(origin, new_text, fontsize=12, color=(0, 0, 0))
                                
        # --- 3. העלמת פתרונות ---
        if hide_solutions:
            sol_rects = page.search_for("פתרון")
            q_rects = page.search_for("שאלה")
            
            events = [(r.y0, 'start', r) for r in sol_rects] + [(r.y0, 'end', r) for r in q_rects]
            events.sort(key=lambda e: e[0])
            
            rects_to_hide = []
            
            if hide_active:
                current_y = 0
                
            for y0, event_type, r in events:
                if event_type == 'start' and not hide_active:
                    hide_active = True
                    rects_to_hide.append(fitz.Rect(0, r.y0 - 2, r.x1 + 2, r.y1 + 2))
                    current_y = r.y1 + 2
                elif event_type == 'end' and hide_active:
                    hide_active = False
                    rects_to_hide.append(fitz.Rect(0, current_y, page.rect.width, max(0, r.y0 - 2)))
                    current_y = None
                    
            if hide_active and current_y is not None:
                rects_to_hide.append(fitz.Rect(0, current_y, page.rect.width, page.rect.height))
                
            for r in rects_to_hide:
                page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))

    output_pdf = io.BytesIO()
    doc.save(output_pdf)
    doc.close()
    
    return output_pdf.getvalue()

# --- עיצוב ממשק המשתמש של האפליקציה (Streamlit) ---
st.title("מנקה המבחנים האולטימטיבי 📄✨")
st.write("העלה קובץ PDF ובחר אילו פעולות תרצה לבצע עליו כדי להכין אותו לתרגול.")

remove_markers_cb = st.checkbox("מחק מרקרים, מסגרות וסימונים צבעוניים", value=True)
shrink_letters_cb = st.checkbox("החלף את כל אותיות התשובה (א, ב, ג...) לאנגלית (A, B, C...) ויישר את גודלן", value=True)
hide_solutions_cb = st.checkbox("הסתר את הפתרונות המלאים (ממחק מהמילה 'פתרון' ועד 'שאלה' הבאה)", value=True)

uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    if st.button("נקה את המבחן"):
        with st.spinner("מעבד את הקובץ..."):
            
            cleaned_pdf_bytes = process_pdf(
                uploaded_file.read(), 
                remove_markers_cb, 
                shrink_letters_cb, 
                hide_solutions_cb
            )
            
            st.success("הקובץ נוקה בהצלחה!")
            
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"clean_{uploaded_file.name}",
                mime="application/pdf"
            )
