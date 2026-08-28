import streamlit as st
import fitz  # PyMuPDF
import io

# --- מילון המרה מורחב וחכם ---
hebrew_to_english = {
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.',
    '.א': '.A', '.ב': '.B', '.ג': '.C', '.ד': '.D', '.ה': '.E', '.ו': '.F',
    'א)': 'A)', 'ב)': 'B)', 'ג)': 'C)', 'ד)': 'D)', 'ה)': 'E)', 'ו)': 'F)',
    '(א)': '(A)', '(ב)': '(B)', '(ג)': '(C)', '(ד)': '(D)', '(ה)': '(E)', '(ו)': '(F)'
}

def process_pdf(pdf_bytes, remove_yellow_only, remove_all_colors, shrink_letters, hide_solutions):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    hide_active = False 
    current_y = 0
    
    for page in doc:
        # --- 1. מחיקת צורות, מרקרים ומסגרות (לפי בחירת המשתמש) ---
        if remove_yellow_only or remove_all_colors:
            annot = page.first_annot
            while annot:
                next_annot = annot.next
                page.delete_annot(annot)
                annot = next_annot
                
            paths = page.get_drawings()
            for p in paths:
                color = p.get("color")
                fill = p.get("fill")
                
                def should_remove(c):
                    if c is None: return False
                    r, g, b = c
                    
                    if remove_all_colors:
                        # מוחק כל צבע שהוא לא שחור או לבן מוחלט
                        if c == (0.0, 0.0, 0.0) or c == (1.0, 1.0, 1.0): return False
                        return True
                    elif remove_yellow_only:
                        # מוחק אך ורק צהוב (כמו מרקרים בפיזיקה)
                        return (r > 0.8 and g > 0.8 and b < 0.5)
                        
                    return False
                    
                if should_remove(color) or should_remove(fill):
                    shape = page.new_shape()
                    for item in p["items"]:
                        if item[0] == "l": 
                            shape.draw_line(item[1], item[2])
                        elif item[0] == "re": 
                            shape.draw_rect(item[1])
                        elif item[0] == "c": 
                            shape.draw_bezier(item[1], item[2], item[3], item[4])
                        elif item[0] == "q": 
                            shape.draw_quad(item[1])
                    
                    original_width = p.get("width")
                    safe_width = original_width if original_width is not None else 1.0
                    
                    shape.finish(
                        color=(1, 1, 1) if color else None,
                        fill=(1, 1, 1) if fill else None,
                        width=safe_width + 1.0
                    )
                    shape.commit()

        # --- 2. המרת אותיות למקבילות באנגלית ---
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
                                
                                rect.y1 += 5.0
                                rect.x0 -= 2.0
                                rect.x1 += 2.0
                                
                                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                new_text = hebrew_to_english[clean_text]
                                page.insert_text(origin, new_text, fontsize=12, color=(0, 0, 0))
                                
        # --- 3. העלמת פתרונות מלאים ---
        if hide_solutions:
            sol_rects = page.search_for("פתרון") + page.search_for("קווים מנחים")
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

remove_yellow_cb = st.checkbox("מחק מרקרים צהובים בלבד (בטוח לפיזיקה ולשרטוטים)", value=True)
remove_all_cb = st.checkbox("מחק את כל הצבעים, המסגרות והצורות (אגרסיבי - למבחנים באלגברה)", value=False)
shrink_letters_cb = st.checkbox("החלף אותיות תשובה (א, ב, ג...) לאנגלית (A, B, C...) ומחק קווים תחתונים", value=True)
hide_solutions_cb = st.checkbox("הסתר את הפתרונות המלאים (גם תחת הכותרת 'קווים מנחים לפיתרון')", value=True)

uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    if st.button("נקה את המבחן"):
        with st.spinner("מעבד את הקובץ..."):
            
            cleaned_pdf_bytes = process_pdf(
                uploaded_file.read(), 
                remove_yellow_cb,
                remove_all_cb,
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
