import streamlit as st
import fitz  # PyMuPDF
import io

def remove_highlights(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    for page in doc:
        # 1. מחיקת הערות רגילות (לכל מקרה, אם נשארו כאלה)
        annot = page.first_annot
        while annot:
            next_annot = annot.next
            page.delete_annot(annot)
            annot = next_annot
            
        # 2. ה"קסם": טיפול במרקרים וקטוריים ("אפויים")
        # מעבר על כל חלקי הקוד הפנימי (Content Streams) של העמוד
        for xref in page.get_contents():
            stream = doc.xref_stream(xref)
            if stream:
                # המרת הקוד לטקסט שניתן לקרוא
                stream_str = stream.decode("latin1")
                
                # בשפת ה-PDF, צבע מוגדר על ידי RGB. צהוב מלא הוא 1 1 0.
                # rg = צבע מילוי (Fill), RG = צבע קו (Stroke)
                # אנחנו מחליפים את הצהוב בלבן מלא (1 1 1) כדי להעלים אותו
                stream_str = stream_str.replace("1 1 0 rg", "1 1 1 rg")
                stream_str = stream_str.replace("1 1 0 RG", "1 1 1 RG")
                
                # למקרה שהתוכנה כתבה את המספרים כעשרוניים:
                stream_str = stream_str.replace("1.0 1.0 0.0 rg", "1.0 1.0 1.0 rg")
                stream_str = stream_str.replace("1.0 1.0 0.0 RG", "1.0 1.0 1.0 RG")
                
                # עדכון הקוד חזרה לתוך העמוד
                doc.update_stream(xref, stream_str.encode("latin1"))

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
