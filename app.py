import streamlit as st
import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
import tempfile


# PAGE CONFIGURATION


st.set_page_config(
    page_title="AI Document Auditor",
    layout="wide",
    page_icon="📄"
)


# APP HEADER


st.title("📄 AI Context-Aware Document Auditor")

st.markdown(
    "Upload complex documents such as contracts, financial reports, "
    "or source-code files to automatically audit and identify "
    "missing information, risks, inconsistencies, and important clauses."
)


# SIDEBAR CONFIGURATION


st.sidebar.header("⚙️ Configuration")

groq_api_key = st.sidebar.text_input(
    "Enter Groq API Key",
    type="password",
    value=os.environ.get("GROQ_API_KEY", ""),
    help="Get your free API key at https://console.groq.com"
)


# LLM MODEL

model_choice = st.sidebar.selectbox(
    "Select LLM Model",
    [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemma2-9b-it",
        "mixtral-8x7b-32768"
    ],
    index=0
)


# CONTEXT SIZE


context_size = st.sidebar.selectbox(
    "Context Size",
    [
        2048,
        4096
    ],
    index=0
)


# CHUNK SETTINGS


chunk_size = st.sidebar.slider(
    "Chunk Size",
    min_value=500,
    max_value=1500,
    value=800,
    step=100
)

chunk_overlap = st.sidebar.slider(
    "Chunk Overlap",
    min_value=50,
    max_value=300,
    value=100,
    step=50
)


# AUDIT TEMPLATES

st.sidebar.header("📋 Quick Audit Templates")

template_type = st.sidebar.selectbox(
    "Choose a preset rule set:",
    [
        "Custom Query",
        "Legal Contract NDA Audit",
        "Financial Statement Health Check",
        "Code Quality & Security Review"
    ]
)

preset_prompts = {

    "Custom Query":
        "",

    "Legal Contract NDA Audit":
        """
Perform an evidence-based contract audit.

Identify:
- Parties involved
- Missing party information
- Important dates
- Blank fields and placeholders
- Referenced documents
- Liability clauses
- Termination clauses
- Payment obligations
- Confidentiality/NDA provisions
- Indemnity provisions
- Renewal provisions
- Compliance requirements
- Potential risks explicitly supported by the document

Do not invent or assume any information.
""",

    "Financial Statement Health Check":
        """
Review the financial document using only the provided document context.

Identify:
- Financial figures
- Missing values
- Numerical inconsistencies
- Unusual changes
- Important financial obligations
- Explicit compliance requirements
- Explicit risks

Do not invent numbers or assumptions.
""",

    "Code Quality & Security Review":
        """
Review the provided source code.

Identify:
- Bugs
- Security vulnerabilities
- Hardcoded credentials
- Injection risks
- Missing error handling
- Memory/resource issues
- Logical problems

Only report issues supported by the provided code context.
Do not invent vulnerabilities.
"""
}


# MAIN APPLICATION


if not groq_api_key:

    st.info(
        "💡 Please enter your Groq API Key in the sidebar. "
        "Get a free key at [console.groq.com](https://console.groq.com)"
    )

else:


   
    # FILE UPLOAD
    

    uploaded_file = st.file_uploader(
        "Upload Document (PDF, TXT, PY, JAVA)",
        type=[
            "pdf",
            "txt",
            "py",
            "java"
        ]
    )

    if uploaded_file:

        with st.spinner(
            "Processing document, extracting text, and creating embeddings..."
        ):

            try:

                
                # SAVE UPLOADED FILE TEMPORARILY
                

                file_extension = uploaded_file.name.split(".")[-1]

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=f".{file_extension}"
                ) as temp_file:

                    temp_file.write(
                        uploaded_file.getbuffer()
                    )

                    temp_file_path = temp_file.name

              
                # LOAD DOCUMENT
              

                if uploaded_file.name.lower().endswith(".pdf"):

                    loader = PyPDFLoader(
                        temp_file_path
                    )

                else:

                    loader = TextLoader(
                        temp_file_path,
                        encoding="utf-8"
                    )

                docs = loader.load()

              
                # REMOVE TEMP FILE
                

                os.unlink(temp_file_path)

               
                # SPLIT DOCUMENT INTO CHUNKS
               
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )

                final_documents = text_splitter.split_documents(
                    docs
                )

                
                # CREATE EMBEDDINGS (HuggingFace - runs locally, no API needed)
                

                embeddings = HuggingFaceEmbeddings(
                    model_name="all-MiniLM-L6-v2"
                )

                
                # CREATE FAISS VECTOR DATABASE
                
                vector_store = FAISS.from_documents(
                    final_documents,
                    embeddings
                )

               
                # RETRIEVER
               
                retriever = vector_store.as_retriever(
                    search_kwargs={
                        "k": 4
                    }
                )

                
                # INITIALIZE LLM (Groq - cloud hosted, free tier)
                
                llm = ChatGroq(
                    api_key=groq_api_key,
                    model_name=model_choice,
                    temperature=0,
                    max_tokens=context_size
                )

                
                # STRICT AUDIT SYSTEM PROMPT
                

                system_prompt = """
You are a strict evidence-based document auditor.

Your most important rule is:

USE ONLY INFORMATION THAT IS EXPLICITLY PRESENT IN THE
PROVIDED DOCUMENT CONTEXT.

Do NOT use general knowledge to fill gaps.

Do NOT invent:
- names
- dates
- addresses
- risks
- obligations
- clauses
- legal requirements
- financial information
- security vulnerabilities
- recommendations presented as facts

If information is not present in the provided context, write:

"Not found in the provided document context."

If a field contains:

or another blank/placeholder,

classify it as:

"MISSING / NOT PROVIDED"

Do not treat a placeholder as actual information.

IMPORTANT:

A potential risk can only be reported if there is evidence
in the provided document context supporting that risk.

For every risk, provide:

Risk:
Evidence:
Why it matters:

If there is not enough evidence to identify a risk, write:

"No specific risk can be established from the provided context."

Do not claim that the document contains something when the
provided context does not contain it.

Do not make assumptions.

Do not repeat the same finding.

OUTPUT FORMAT


## 1. Explicit Information

List only facts directly present in the document context.

## 2. Missing / Blank Information

List fields that are blank, incomplete, or represented
by placeholders.

## 3. Referenced Documents

List only documents explicitly referenced in the context.

## 4. Evidence-Based Risks

List only risks directly supported by the context.

For every risk:

Risk:
Evidence:
Why it matters:

If there are no supported risks:

"No specific risk can be established from the provided context."

## 5. Obligations

List only obligations explicitly stated in the context.

## 6. Important Observations

List only observations supported by the context.

## 7. Conclusion

Provide a short conclusion based ONLY on the provided context.



FINAL RULE:

If the answer cannot be found in the provided context,
DO NOT GUESS.

Say:

"Not found in the provided document context."
"""
                
                # SUCCESS MESSAGE
                
                st.success(
                    f"Successfully indexed '{uploaded_file.name}' "
                    f"into the vector database!"
                )

                st.caption(
                    f"📄 Pages/sections loaded: {len(docs)} | "
                    f"🔹 Chunks created: {len(final_documents)} | "
                    f"🧠 Model: {model_choice}"
                )

                
                # AUDIT ENGINE
                
                st.subheader("🔍 Run Audit Engine")

                default_query = preset_prompts[
                    template_type
                ]

                user_query = st.text_area(
                    "Specify what you want to audit or verify:",
                    value=default_query,
                    height=180
                )

                
                # EXECUTE AUDIT
                

                if st.button(
                    "🚀 Execute Audit Analysis",
                    use_container_width=True
                ):

                    if not user_query.strip():

                        st.warning(
                            "Please enter a query or choose an audit template."
                        )

                    else:

                        with st.spinner(
                            "🔎 Retrieving relevant document evidence..."
                        ):

                            
                            # RETRIEVE DOCUMENT CHUNKS
                            

                            relevant_docs = retriever.invoke(
                                user_query
                            )

                        if not relevant_docs:

                            st.warning(
                                "No relevant information was found "
                                "in the uploaded document."
                            )

                        else:

                            with st.spinner(
                                "🤖 LLM is analyzing the document evidence..."
                            ):

                               
                                # FORMAT CONTEXT
                            

                                context_parts = []

                                for i, doc in enumerate(
                                    relevant_docs
                                ):

                                    context_parts.append(
                                        f"""
SOURCE CHUNK {i + 1}

{doc.page_content}
"""
                                    )

                                context_text = "\n".join(
                                    context_parts
                                )

                                
                                # FINAL PROMPT
                                

                                full_prompt = f"""
{system_prompt}


DOCUMENT CONTEXT


{context_text}


USER QUERY


{user_query}


INSTRUCTIONS


Answer the user's query using ONLY the document context above.

Do not use external knowledge.

Do not guess.

Do not fabricate missing information.

If information is not available in the context,
say:

"Not found in the provided document context."

Now produce the audit report.
"""

                              
                                # LLM CALL
                               

                                response = llm.invoke(
                                    full_prompt
                                )

                               
                                # DISPLAY REPORT
                               

                                st.markdown(
                                    "### 📊 System Audit Report"
                                )

                                st.markdown("---")

                                st.markdown(
                                    response.content
                                )

                                st.markdown("---")

                                
                                # SOURCE DOCUMENT CHUNKS
                               

                                with st.expander(
                                    "👁️ View Source Document Chunks "
                                    "Used in This Inference"
                                ):

                                    for i, doc in enumerate(
                                        relevant_docs
                                    ):

                                        st.markdown(
                                            f"### Chunk {i + 1}"
                                        )

                                        st.caption(
                                            doc.page_content
                                        )

                                        st.markdown("---")

           
            # ERROR HANDLING
           

            except Exception as e:

                st.error(
                    f"An error occurred during execution: {str(e)}"
                )