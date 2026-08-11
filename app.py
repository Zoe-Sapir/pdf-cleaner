import streamlit as st
import fitz  # PyMuPDF
import io

# --- מילון המרה מאותיות בעברית לאנגלית ---
hebrew_to_english = {
    'א': 'A', 'ב': 'B', 'ג': 'C', 'ד': 'D', 'ה': 'E', 'ו': 'F',
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.'
}

def process_pdf(pdf_bytes, remove_markers, shrink_letters, hide_solutions):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # משתנה שיזכור אם אנחנו "באמצע הסתרת פתרון". 
    # זה מאפשר לפתרונות להיות מוסתרים גם אם הם נחתכים ועוברים לעמוד הבא!
    hide_active = False 
    
    for page in doc:
        # --- 1. מחיקת מרקרים צהובים (צורות וקטוריות) ---
        if remove_markers:
            for xref in page.get_contents():
                stream = doc.xref_stream(xref)
                if stream:
                    stream_str = stream.decode("latin1")
                    stream_str = stream_str.replace("1 1 0 rg", "1 1 1 rg")
                    stream_str = stream_str.replace("1 1 0 RG", "1 1 1 RG")
                    stream_str = stream_str.replace("1.0 1.0 0.0 rg", "1.0 1.0 1.0 rg")
                    stream_str = stream_str.replace("1.0 1.0 0.0 RG", "1.0 1.0 1.0 RG")
                    doc.update_stream(xref, stream_str.encode("latin1"))
                    
        # --- 2. המרת כל אותיות התשובה לאנגלית ויישורן ---
        if shrink_letters:
            dict_data = page.get_text("dict")
            for block in dict_data["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            original_text = span["text"].strip()
                            clean_text = original_text.replace(" ", "")
                            
                            if clean_text in hebrew_to_english:
                                rect = fitz.Rect(span["bbox"])
                                origin = span["origin"]
                                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                new_text = hebrew_to_english[clean_text]
                                page.insert_text(origin, new_text, fontsize=12, color=(0, 0, 0))
                                
        # --- 3. העלמת פתרונות (מ"פתרון" ועד "שאלה") ---
        if hide_solutions:
            # מחפש את הקואורדינטות של כל המילים "פתרון" ו"שאלה" בעמוד
            sol_rects = page.search_for("פתרון")
            q_rects = page.search_for("שאלה")
            
            # יוצר רשימה של אירועים לפי הגובה שלהם בעמוד (y0)
            events = [(r.y0, 'start') for r in sol_rects] + [(r.y0, 'end') for r in q_rects]
            # ממיין מלמעלה למטה
            events.sort(key=lambda e: e[0])
            
            rects_to_hide = []
            current_y = 0 if hide_active else None
            
            for y, event_type in events:
                if event_type == 'start' and not hide_active:
                    hide_active = True
                    # מתחיל קצת מעל המילה כדי שהמלבן הלבן יכסה אותה לחלוטין
                    current_y = max(0, y - 5) 
                elif event_type == 'end' and hide_active:
                    hide_active = False
                    # סוגר את אזור המחיקה קצת מעל המילה "שאלה"
                    rects_to_hide.append(fitz.Rect(0, current_y, page.rect.width, max(0, y - 5)))
                    current_y = None
                    
            # אם סיימנו את העמוד אבל עדיין לא מצאנו "שאלה", נסתיר עד סוף העמוד!
            if hide_active:
                rects_to_hide.append(fitz.Rect(0, current_y, page.rect.width, page.rect.height))
                
            # ציור המלבנים הלבנים בפועל על גבי ה-PDF
            for r in rects_to_hide:
                page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))

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
hide_solutions_cb = st.checkbox("הסתר את הפתרונות המלאים (ממחק מהמילה 'פתרון' ועד 'שאלה' הבאה)", value=True)

# כפתור העלאת קובץ
uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    # כפתור התחלת פעולה
    if st.button("נקה את המבחן"):
        with st.spinner("מעבד את הקובץ..."):
            
            # קריאה לפונקציה המשולבת שלנו
            cleaned_pdf_bytes = process_pdf(
                uploaded_file.read(), 
                remove_markers_cb, 
                shrink_letters_cb, 
                hide_solutions_cb
            )
            
            st.success("הקובץ נוקה בהצלחה!")
            
            # כפתור הורדת הקובץ הנקי
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"clean_{uploaded_file.name}",
                mime="application/pdf"
            )
