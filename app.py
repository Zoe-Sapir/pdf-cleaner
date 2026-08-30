import streamlit as st
import fitz  # PyMuPDF
import io
import re
import random

# --- מילון המרה מורחב וחכם ---
hebrew_to_english = {
    'א.': 'A.', 'ב.': 'B.', 'ג.': 'C.', 'ד.': 'D.', 'ה.': 'E.', 'ו.': 'F.',
    '.א': '.A', '.ב': '.B', '.ג': '.C', '.ד': '.D', '.ה': '.E', '.ו': '.F',
    'א)': 'A)', 'ב)': 'B)', 'ג)': 'C)', 'ד)': 'D)', 'ה)': 'E)', 'ו)': 'F)',
    '(א)': '(A)', '(ב)': '(B)', '(ג)': '(C)', '(ד)': '(D)', '(ה)': '(E)', '(ו)': '(F)'
}

# תבניות לזיהוי צבעים
NUM = r'[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)'
RGB_PATTERN = re.compile(rf'\b({NUM})\s+({NUM})\s+({NUM})\s+(rg|RG)\b')
CMYK_PATTERN = re.compile(rf'\b({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+(k|K)\b')

def process_pdf(pdf_bytes, remove_yellow_cb, remove_all_cb, shrink_letters_cb, hide_solutions_cb, shuffle_answers_cb):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    hide_active = False 
    current_y = 0
    
    for page in doc:
        # --- 1. מחיקת מרקרים וצבעים ---
        if remove_yellow_cb or remove_all_cb:
            annot = page.first_annot
            while annot:
                next_annot = annot.next
                page.delete_annot(annot)
                annot = next_annot
                
            def clean_rgb(match):
                try:
                    r, g, b = float(match.group(1)), float(match.group(2)), float(match.group(3))
                    op = match.group(4)
                    if (r == 0.0 and g == 0.0 and b == 0.0) or (r == 1.0 and g == 1.0 and b == 1.0): return match.group(0)
                    if remove_all_cb: return f"1 1 1 {op}"
                    elif remove_yellow_cb and r > 0.8 and g > 0.8 and b < 0.5: return f"1 1 1 {op}"
                    return match.group(0)
                except: return match.group(0)

            def clean_cmyk(match):
                try:
                    c, m, y, k = float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))
                    op = match.group(5)
                    if (c == 0.0 and m == 0.0 and y == 0.0 and k == 1.0) or (c == 0.0 and m == 0.0 and y == 0.0 and k == 0.0): return match.group(0)
                    if remove_all_cb: return f"0 0 0 0 {op}"
                    elif remove_yellow_cb and c < 0.2 and m < 0.2 and y > 0.8 and k < 0.2: return f"0 0 0 0 {op}"
                    return match.group(0)
                except: return match.group(0)

            for xref in page.get_contents():
                stream = doc.xref_stream(xref)
                if stream:
                    stream_str = stream.decode("latin1")
                    stream_str = RGB_PATTERN.sub(clean_rgb, stream_str)
                    stream_str = CMYK_PATTERN.sub(clean_cmyk, stream_str)
                    doc.update_stream(xref, stream_str.encode("latin1"))

        # --- 2. המרת אותיות, מחיקת קווים תחתונים וערבוב תשובות ---
        if shrink_letters_cb or shuffle_answers_cb:
            dict_data = page.get_text("dict")
            
            # שלב א': איסוף וזיהוי כל התשובות בעמוד
            page_answers = [] # רשימה שתשמור מידע על כל תשובה שמצאנו
            blocks = dict_data["blocks"]
            
            for b_idx, block in enumerate(blocks):
                if "lines" in block:
                    for l_idx, line in enumerate(block["lines"]):
                        for s_idx, span in enumerate(line["spans"]):
                            original_text = span["text"].strip()
                            clean_text = original_text.replace(" ", "")
                            
                            # אם זה אות תשובה (כמו א., ב. וכו')
                            if clean_text in hebrew_to_english:
                                # נשמור את המיקום שלה
                                ans_letter_rect = fitz.Rect(span["bbox"])
                                ans_letter_origin = span["origin"]
                                ans_letter_text = hebrew_to_english[clean_text] if shrink_letters_cb else original_text
                                
                                # עכשיו ננסה למצוא את "הטקסט של התשובה" שצמוד אליה
                                # לרוב הוא נמצא באותו בלוק, או ממש בסמוך אליו
                                answer_content_text = ""
                                answer_content_rect = None
                                
                                # סריקה מקומית לאיסוף הטקסט ששייך לתשובה הזו
                                for local_span in line["spans"]:
                                    if local_span != span:
                                        answer_content_text += local_span["text"]
                                        if answer_content_rect is None:
                                            answer_content_rect = fitz.Rect(local_span["bbox"])
                                        else:
                                            answer_content_rect.include_rect(fitz.Rect(local_span["bbox"]))
                                
                                # אם לא מצאנו טקסט באותה שורה, נחפש בסביבה הקרובה
                                if not answer_content_text.strip():
                                    for nearby_block in blocks:
                                        if "lines" in nearby_block:
                                            for nearby_line in nearby_block["lines"]:
                                                for nearby_span in nearby_line["spans"]:
                                                    # בודק אם הטקסט קרוב מספיק (באותו אזור y ומעט שמאלה)
                                                    n_rect = fitz.Rect(nearby_span["bbox"])
                                                    if abs(n_rect.y0 - ans_letter_rect.y0) < 5 and n_rect.x1 < ans_letter_rect.x0:
                                                        answer_content_text += nearby_span["text"]
                                                        if answer_content_rect is None:
                                                            answer_content_rect = n_rect
                                                        else:
                                                            answer_content_rect.include_rect(n_rect)
                                                            
                                page_answers.append({
                                    "letter_text": ans_letter_text,
                                    "letter_rect": ans_letter_rect,
                                    "letter_origin": ans_letter_origin,
                                    "content_text": answer_content_text,
                                    "content_rect": answer_content_rect
                                })
            
            # שלב ב': קיבוץ לתשובות ששייכות לאותה שאלה (לפי גובה Y)
            questions = []
            if page_answers:
                # מיון לפי Y (כדי לאסוף שאלות מלמעלה למטה)
                page_answers.sort(key=lambda x: x["letter_rect"].y0)
                
                current_question = [page_answers[0]]
                for i in range(1, len(page_answers)):
                    # אם המרחק האנכי (Y) מהתשובה הקודמת גדול מ-50 פיקסלים, זו כנראה שאלה חדשה
                    if abs(page_answers[i]["letter_rect"].y0 - current_question[-1]["letter_rect"].y0) > 50:
                        questions.append(current_question)
                        current_question = [page_answers[i]]
                    else:
                        current_question.append(page_answers[i])
                questions.append(current_question)
            
            # שלב ג': מחיקה וציור מחדש (עם ערבוב אם נבחר)
            for question_answers in questions:
                # שומרים את המיקומים (המשבצות שבהן נצייר)
                locations = [{"letter_origin": a["letter_origin"], "content_rect": a["content_rect"]} for a in question_answers]
                
                # שומרים את התוכן
                contents = [{"letter_text": a["letter_text"], "content_text": a["content_text"]} for a in question_answers]
                
                if shuffle_answers_cb:
                    random.shuffle(contents)
                
                for loc, cont in zip(locations, contents):
                    # 1. מחיקת האות המקורית (עם הרחבה למטה לטובת מחיקת קווים תחתונים)
                    # מאתרים מחדש את האזור למחיקה לפי ה-origin
                    clean_rect = fitz.Rect(loc["letter_origin"][0] - 15, loc["letter_origin"][1] - 15, loc["letter_origin"][0] + 15, loc["letter_origin"][1] + 5)
                    page.draw_rect(clean_rect, color=(1, 1, 1), fill=(1, 1, 1))
                    
                    # 2. ציור האות החדשה
                    page.insert_text(loc["letter_origin"], cont["letter_text"], fontsize=12, color=(0, 0, 0))
                    
                    # 3. אם יש טקסט תוכן לתשובה - נמחוק אותו ונצייר את המעורבב
                    if loc["content_rect"] and cont["content_text"].strip():
                        # מחיקת התוכן הישן
                        page.draw_rect(loc["content_rect"], color=(1, 1, 1), fill=(1, 1, 1))
                        # נסיון לצייר את התוכן החדש בדיוק באותו מקום (זה עשוי להיות מעט מורכב בגלל פונטים וגדלים)
                        # לבינתיים, כדי לא לפגוע בנוסחאות מורכבות שמפוענחות כטקסט פשוט, 
                        # נכתוב את הטקסט הפשוט. שימי לב: זה לא יעבוד מושלם על שברים או מטריצות!
                        try:
                           page.insert_text((loc["content_rect"].x0, loc["content_rect"].y1 - 2), cont["content_text"], fontsize=10, color=(0, 0, 0))
                        except Exception as e:
                            pass # אם יש בעיה בקידוד, נדלג כדי לא להקריס

        # --- 3. העלמת פתרונות מלאים ---
        if hide_solutions_cb:
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
shuffle_answers_cb = st.checkbox("ערבב את סדר התשובות (מנסה לערבב תשובות באותה שאלה)", value=False)
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
                hide_solutions_cb,
                shuffle_answers_cb
            )
            
            st.success("הקובץ נוקה בהצלחה!")
            
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"clean_{uploaded_file.name}",
                mime="application/pdf"
            )
