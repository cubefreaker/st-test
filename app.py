import os, jwt
import streamlit as st
from google.cloud import bigquery
import mysql.connector
import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("GCP_REGION")

# def get_db_connection():
#     conn = mysql.connector.connect(
#         host=os.environ.get("QA_DB_HOST"),
#         user=os.environ.get("QA_DB_USER"),
#         password=os.environ.get("QA_DB_PASS"),
#         database=os.environ.get("QA_DB_NAME"),
#         port=os.environ.get("QA_DB_PORT")
#     )
#     return conn

def get_data_from_db(query):
    client = bigquery.Client()
    return client.query(query, project=PROJECT_ID).to_dataframe()

# def get_data_from_db(query):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute(query)
#     rows = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return rows

def get_gemini_response(question, prompt):
    model = GenerativeModel('gemini-pro')
    response = model.generate_content([prompt, question])
    return response.text

def auth_data():
    data = None
    if 't' in st.query_params:
        token = st.query_params.t
        try:    
            data = jwt.decode(token, os.environ.get("JWT_KEY"), algorithms=["HS256"])
        except:
            pass
    return data

def show_chat_page():
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    to_sql_prompt = f"""
        Kamu adalah seorang expert dalam mengubah pertanyaan dalam bahasa indonesia menjadi query MYSQL!
        
        Jika pertanyaan tidak ada hubungannya dengan konteks data maka kamu akan menjawab: "Maaf, saya hanya bisa menjawab pertanyaan mengenai data penjualan invoice"

        Kamu diberikan tabel dengan nama {os.environ.get('TABLE_SOURCE')} yang mempunyai kolom sebagai berikut:
        - product (tipe atau nama produk)
        - invoice_no (nomor invoice)
        - inv_date (tanggal invoice dibuat)
        - due_date (tenggat waktu pembayaran invoice)
        - customer_name (nama customer)\
        - sellprice (harga jual)
        - outstanding (sisa pembayaran)
        - payment_status (status pembayaran)

        Contoh:
        1.  Pertanyaan: Berapa jumlah total invoice keseluruhan?
            Query: SELECT COUNT(*) FROM {os.environ.get('TABLE_SOURCE')}
        2.  Pertanyaan: Berapa Jumlah customer atau pelanggan dari semua invoice?
            Query: SELECT COUNT(*) FROM {os.environ.get('TABLE_SOURCE')} GROUP BY customer_name
        3.  Pertanyaan: Berapa jumlah total penjualan pada bulan januari?
            Query: SELECT SUM(sellprice) AS sellprice FROM {os.environ.get('TABLE_SOURCE')} WHERE inv_date BETWEEN '2024-01-01' AND '2024-01-31'
        4.  Pertanyaan: Berapa penjualan dari customer Yokogawa Indonesia, PT?
            Query: SELECT SUM(sellprice) AS sellprice FROM {os.environ.get('TABLE_SOURCE')} WHERE customer_name = 'Yokogawa Indonesia, PT'

        Berikan hasil query sql tanpa tanda ``` dan juga tanpa penjelasan apapun, hanya kode sql nya saja!
    """

    from_sql_prompt = f"""
        Kamu adalah seorang expert dalam mengubah data dari hasil query database ke dalam bahasa indonesia!

        Contoh:
        1.  Pertanyaan: Berapa jumlah total invoice keseluruhan?
            Query: SELECT COUNT(*) FROM {os.environ.get('TABLE_SOURCE')}
            Hasil: [(1000,)]
            Jawaban: Jumlah total invoice keseluruhan adalah (Hasil) invoice
        2.  Pertanyaan: Berapa Jumlah customer atau pelanggan dari semua invoice?
            Query: SELECT COUNT(*) FROM {os.environ.get('TABLE_SOURCE')} GROUP BY customer_name
            Hasil: [(1000,)]
            Jawaban: Jumlah total customer atau pelanggan yang terdapat pada invoice adalah (Hasil) customer
        3.  Pertanyaan: Berapa jumlah total penjualan pada bulan januari?
            Query: SELECT SUM(sellprice) AS sellprice FROM {os.environ.get('TABLE_SOURCE')} WHERE inv_date BETWEEN '2024-01-01' AND '2024-01-31'
            Hasil: [(1000,)]
            Jawaban: Jumlah total penjualan pada bulan januari tahun [tahun] adalah Rp. (Hasil dalam format kurs)
        4.  Pertanyaan: Berapa penjualan dari customer Yokogawa Indonesia, PT?
            Query: SELECT SUM(sellprice) AS sellprice FROM {os.environ.get('TABLE_SOURCE')} WHERE customer_name = 'Yokogawa Indonesia, PT'
            Hasil: [(1000,)]
            Jawaban: Jumlah total penjualan dari customer Yokogawa Indonesia, PT adalah Rp. (Hasil dalam format kurs)
        
        Peraturan jawaban:
        1. Berikan hasil dalam satu kalimat ringkas dan jelas sesuai dengan konteks pertanyaan dan contoh jawaban
        2. Jangan ada informasi terkait query maupun nama tabel!
        3. Jika ada nominal angka terkait penjualan, pakai format penulisan kurs mata uang
    """

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("Silahkan bertanya"):
        with st.chat_message("user"):
            st.markdown(question)
        
        st.session_state.messages.append({"role": "user", "content": question})

        with st.chat_message("assistant"):
            with st.status("Mencari jawaban"):
                # question = input('Question: ')
                resp_query = get_gemini_response(question, to_sql_prompt)
                resp_query = resp_query.replace('```sql', '').replace('```', '').strip()
                # print('Query: ', resp_query, '\n')
                try:
                    result_query = get_data_from_db(resp_query)
                    final_question = f"""
                        Pertanyaan: {question}
                        Query: {resp_query}
                        Hasil: {str(result_query)}
                    """
                    # print(final_question, '\n')

                    resp_final = get_gemini_response(final_question, from_sql_prompt)
                except:
                    resp_final = resp_query

                # print('Final Result: ', resp_final, '\n')
            st.markdown(resp_final)

        st.session_state.messages.append({"role": "assistant", "content": resp_final})

def show_unauth_page():
    st.write("Page Not Found!")

if __name__ == "__main__":
    st.set_page_config(page_title="Opsifin Bot")
    # st.header("Opsifin personal assistant")

    st.markdown("""
        <style>
            header {
                visibility: hidden;
            }
            
            .stMainBlockContainer, .stChatMessage {
                width: 100%;
                padding: 10px 0;
            }
                
            .st-emotion-cache-1c7y2kd {
                flex-direction: row-reverse;
            }
        </style>
    """, unsafe_allow_html=True)

    data = auth_data()
    
    if data:
        show_chat_page()
    else:
        show_unauth_page()
