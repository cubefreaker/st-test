import os, jwt, requests
import prompts
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import bigquery
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT")
LOCATION = os.getenv("GCP_REGION")
API_KEY = os.getenv('API_SECRET_KEY')

def get_data_from_db(query):
    client = bigquery.Client()
    return client.query(query, project=PROJECT_ID).to_dataframe()

def get_gemini_response(question, prompt):
    model = GenerativeModel('gemini-1.5-pro')
    response = model.generate_content([prompt, question])
    return response.text

def auth_data():
    data = None
    if 't' in st.query_params:
        token = st.query_params.t
        try:    
            decoded_token = jwt.decode(token, os.getenv("JWT_KEY"), algorithms=["HS256"])
            if decoded_token['access_chatbot'] == 'True':
                data = check_data(decoded_token)
        except:
            print('error')
            pass
    return data

def check_data(data):
    result = None
    try:
        url = f"{data['iss']}api/checkUserLoginToken"
        headers = {
            "Content-Type": "application/json",
            "Secret": API_KEY
        }
        payload = {
            "userid": data['userid']
        }
        response = requests.post(url, headers=headers, json=payload).json()
        print(response)
        result = response['data']
    except:
        pass

    return result

def show_chat_page():
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    to_sql_prompt = prompts.text_to_sql(os.getenv('TABLE_SOURCE'))
    from_sql_prompt = prompts.sql_to_text(os.getenv('TABLE_SOURCE'))

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
                print(resp_query)
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
    
    if not data:
        show_unauth_page()
    elif data['has_access']:
        show_chat_page()
    else:
        show_unauth_page()