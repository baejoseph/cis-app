import streamlit as st
from openai_services import OpenAIEmbeddingService, OpenAIGenerationService
from rag_pipeline import (
    RetrievalService, PromptAugmenter, QueryProcessor,
    ProcessorConfig, RetrievalConfig, CosineSimilarity
)
from hashlib import sha256
from dotenv import load_dotenv
import os
import boto3
from log_time import ProcessTimer
from helpers import load_config

pt = ProcessTimer()

load_dotenv()

# === Streamlit Setup ===
st.set_page_config(page_title="CIS Benchmarks Retrieval", layout="wide")
jd_logo = "images/jd-logo.png"
logo_white = "images/logo-white.png"

st.logo(jd_logo, size="large", link="https://jdfortress.com", icon_image=logo_white)

st.title("CIS Benchmarks RAG (Demo)")

API_KEY       = os.getenv("OPENAI_API_KEY")
BUCKET        = load_config("AWS_S3_BUCKET")
VECTOR_BUCKET = load_config("VECTOR_S3_BUCKET")
VECTOR_REGION = load_config("VECTOR_REGION")
VECTOR_INDEX  = load_config("VECTOR_INDEX")
VECTOR_DIM    = load_config("VECTOR_DIMENSION")

# Simple hardcoded auth
USER = os.getenv("DEMO_USERNAME")
PASSWORD = os.getenv("DEMO_PASSWORD")

def check_password():
    def password_entered():
        if sha256((st.session_state["username"] + st.session_state["password"]).encode()).hexdigest() == sha256((USER+PASSWORD).encode()).hexdigest():
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Username", value="", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.error("❌ Incorrect password")
        st.stop()

check_password()


# === Session State Initialization ===
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "base_services" not in st.session_state:
    with st.spinner("Initializing LLM..."):
        session = boto3.Session(region_name=VECTOR_REGION)
        s3_client = session.client("s3")
        vector_svc = session.client("s3vectors")
        embedding_service = OpenAIEmbeddingService(API_KEY, load_config('embedding_model'))
        generation_service = OpenAIGenerationService(API_KEY, load_config('inference_model'))
        similarity_metric = CosineSimilarity()
        retrieval_service = RetrievalService(
            vector_svc, 
            s3_client,
            load_config('reranker_model')
            )
        augmenter = PromptAugmenter('rag_prompt.md')

        st.session_state.base_services = {
            "aws_session": session,
            "s3_client": s3_client,
            "vector_client": vector_svc,
            "embedding_service": embedding_service,
            "generation_service": generation_service,
            "retrieval_service": retrieval_service,
            "augmenter": augmenter,
        }
    st.success(f"LLM initialized: {generation_service.model}", icon="✅")

# === Pre-processed PDFs Selector ===
#st.sidebar.markdown("---")
#st.sidebar.subheader("🗃️ Select Documents")

# === Retrieval Configuration ===
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Retrieval Settings")
top_k = st.sidebar.slider("Top K Chunks", 1, 10, 3)
similarity_threshold = st.sidebar.slider("Similarity Threshold", 0.0, 1.0, 0.32)

# === Chat Input ===
user_input = st.chat_input("Ask a question...")

if user_input and API_KEY:
    with st.spinner("Generating response..."):
        # Create new processor with current config values
        current_config = ProcessorConfig(
            retrieval=RetrievalConfig(
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
        )
        
        processor = QueryProcessor(
            embedding_service=st.session_state.base_services["embedding_service"],
            retrieval_service=st.session_state.base_services["retrieval_service"],
            prompt_augmenter=st.session_state.base_services["augmenter"],
            generation_service=st.session_state.base_services["generation_service"],
            config=current_config
        )
        
        pt.mark("RAG Processing Query")
        response = processor.process_query(user_input)
        pt.mark("RAG Processing Query")
        st.session_state.chat_history.append({"user": user_input, "bot": response})

# === Display Chat ===
for exchange in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(exchange["user"])
    with st.chat_message("assistant"):
        st.markdown(exchange["bot"])
