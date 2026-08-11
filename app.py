import streamlit as st
import fitz  # PyMuPDF
import io

# --- מילון המרה מורחב ---
hebrew_to_english = {
    'א': 'A', 'ב': 'B', 'ג': 'C', 'ד': 'D', 'ה': 'E', 'ו': 'F',
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.',
    '.א': '.A', '.ב': '.B', '.ג': '.C', '.ד': '.D', '.ה': '.E', '.ו': '.F',
    'א)': 'A)', 'ב)': 'B)', 'ג)': 'C)', 'ד)': 'D)', 'ה)': 'E)', 'ו)': 'F)',
    '(א)': '(A)', '(ב)': '(B)', '(ג)': '(C)', '(ד)': '(D)', '(ה)': '(E)', '(ו)': '(F)'
}

def process_pdf(pdf_bytes, remove_markers, shrink_letters, hide_solutions):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    hide_active = False 
    current_y = 0
    
    for page in doc:
        # --- 1. מחיקת מסגרות, מרקרים וצורות צבעוניות (השיטה החדשה והמוחלטת!) ---
        if remove_markers:
            # א. מחיקת הערות (Annotations) קלאסיות
            annot = page.first_annot
            while annot:
                next_annot = annot.next
                page.delete_annot(annot)
                annot = next_annot
                
            # ב. זיהוי צורות גרפיות (וקטורים) בתוך הדף ומחיקת הצבעוניות שבהן
            paths = page.get_drawings()
            for p in paths:
                color = p.get("color")
                fill = p.get("fill")
                
                def is_colored(c):
                    if c is None: return False
                    # אם זה לא שחור מוחלט ולא לבן מוחלט - זה צבעוני (כמו ירוק או ורוד)
                    if c == (0.0, 0.0, 0.0) or c == (1.0, 1.0, 1.0): return False
                    return True
                    
                if is_colored(color) or is_colored(fill):
                    # יצירת צורה חדשה זהה לחלוטין - אבל בצבע לבן כדי לכסות את הישנה
                    shape = page.new_shape()
                    for item in p["items"]:
                        if item[0] == "l": # קו
                            shape.draw_line(item[1], item[2])
                        elif item[0] == "re": # מלבן
                            shape.draw_rect(item[1])
                        elif item[0] == "c": # עקומה
                            shape.draw_bezier(item[1], item[2], item[3], item[4])
                        elif item[0] == "q": # מרובע
                            shape.draw_quad(item[1])
                    
                    # מציירים את הצורה בלבן, עם קו טיפה יותר עבה כדי לדרוס לחלוטין את המקור
                    shape.finish(
                        color=(1, 1, 1) if color else None,
                        fill=(1, 1, 1) if fill else None,
                        width=p.get("width", 1) + 1.0
                    )
                    shape.commit()

        # --- 2. המרת אותיות למקבילות באנגלית, ומחיקת קווים תחתונים ---
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
                                
                                # הגדלת הריבוע הלבן כלפי מטה כדי "לבלוע" את כל הקווים התחתונים (Underlines)
                                rect.y1 += 5.0
                                rect.x0 -= 2.0
                                rect.x1 += 2.0
                                
                                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                new_text = " ".join(new_words)
                                # ציור הטקסט מחדש בשחור מלא (מתקן גם אם הטקסט המקורי היה ורוד)
                                page.insert_text(origin, new_text, fontsize=12, color=(0, 0, 0))
                                
        # --- 3. העלמת פתרונות מלאים ---
        if hide_solutions:
            # מחפש גם את המילה פתרון וגם "קווים מנחים" כפי שהופיע במסמך
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

# אפשרויות בחירה מעודכנות
remove_markers_cb = st.checkbox("מחק מרקרים ומסגרות (מעלים צורות ירוקות/צבעוניות סוררות!)", value=True)
shrink_letters_cb = st.checkbox("החלף אותיות תשובה (א, ב, ג...) לאנגלית (A, B, C...) ומחק קווים תחתונים", value=True)
hide_solutions_cb = st.checkbox("הסתר את הפתרונות המלאים (גם תחת הכותרת 'קווים מנחים לפיתרון')", value=True)

uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    if st.button("נקה את המבחן"):
        with st.spinner("מעבד את הקובץ (מפעיל אלגוריתם מחיקת וקטורים צבעוניים)..."):
            
            cleaned_pdf_bytes = process_pdf(
                uploaded_file.read(), 
                remove_markers_cb, 
                shrink_letters_cb, 
                hide_solutions_cb
            )
            
            st.success("הקובץ נוקה בהצלחה! הריבוע הירוק היסטוריה.")
            
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"clean_{uploaded_file.name}",
                mime="application/pdf"
            )
