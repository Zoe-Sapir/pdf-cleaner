import streamlit as st
import fitz  # PyMuPDF
import io

def remove_highlights(pdf_bytes):
    # פתיחת קובץ ה-PDF מתוך הזיכרון
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # מעבר על כל העמודים במסמך
    for page in doc:
        # מעבר על כל ההערות (Annotations) בעמוד
        annot = page.first_annot
        while annot:
            next_annot = annot.next
            # סוג 8 מייצג בדרך כלל סימוני הדגשה (Highlight) ב-PDF
            if annot.type[0] == 8: 
                page.delete_annot(annot)
            annot = next_annot
            
    # שמירת הקובץ המעודכן לתוך אובייקט זיכרון חדש
    output_pdf = io.BytesIO()
    doc.save(output_pdf)
    doc.close()
    
    return output_pdf.getvalue()

# --- עיצוב ממשק המשתמש של האפליקציה (Streamlit) ---
st.title("מחק מרקרים מקובצי PDF 🖍️➡️📄")
st.write("העלה קובץ PDF שיש בו סימוני הדגשה (מרקר), והאפליקציה תנקה אותם עבורך.")

# כפתור העלאת קובץ
uploaded_file = st.file_uploader("בחר קובץ PDF", type="pdf")

if uploaded_file is not None:
    st.success("הקובץ הועלה בהצלחה!")
    
    # כפתור התחלת פעולה
    if st.button("נקה מרקרים מהקובץ"):
        with st.spinner("מנקה את הקובץ..."):
            # קריאה לפונקציית הניקוי
            cleaned_pdf_bytes = remove_highlights(uploaded_file.read())
            
            st.success("המרקרים נוקו בהצלחה!")
            
            # כפתור הורדת הקובץ הנקי
            st.download_button(
                label="הורד את הקובץ הנקי 📥",
                data=cleaned_pdf_bytes,
                file_name=f"cleaned_{uploaded_file.name}",
                mime="application/pdf"
            )