# ==============================================================================
# Copyright (c) 2026 Oleksiy Marchenko. All rights reserved.
#
# NOTICE: This source code is provided to the organizers of BrabantHack_26 
# (specifically for the IKNL track evaluation) STRICTLY for demonstration 
# and assessment purposes during the hackathon event.
#
# Full commercial rights, intellectual property, and copyright remain 
# exclusively with the author. No license is granted for commercial use, 
# reproduction, modification, or distribution outside the specific scope 
# of the BrabantHack_26 event evaluation.
# ==============================================================================
import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# --- 1. ЗАГРУЗКА И ОБРАБОТКА PDF ---
def build_vector_db(pdf_paths):
    print("Начинаю загрузку PDF файлов...")
    docs = []
    for path in pdf_paths:
        loader = PyMuPDFLoader(path)
        docs.extend(loader.load())
        print(f"Загружен: {path}")
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(docs)
    
    print("Создаю векторную базу FAISS...")
    embeddings = OpenAIEmbeddings()
    vector_db = FAISS.from_documents(chunks, embeddings)
    return vector_db

# Вспомогательная функция для сборки текста в один абзац
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# --- 2. НАСТРОЙКА ИИ (LCEL ПОДХОД) ---
def get_rag_chain(vector_db):
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0) 
    
    template = """
    You are an expert oncology navigator system for Family OS.
    Analyze the provided context and generate a proactive checklist STRICTLY for the patient's Caregiver.
    Always cite your source (e.g., 'According to [source_name, page X]...').

    CRITICAL RULES (apply in strict order before generating any output):

    RULE 0 — EMERGENCY OVERRIDE (SCORE 4+): Check the Distress Score. If it is 4 or higher, this rule OVERRIDES ALL OTHER RULES. Do NOT search the Context for matching issues. You MUST output EXACTLY these 3 sections and NOTHING else:
    1. Red Flags: "URGENT: Patient reports severe distress (Score 4+). Medical escalation initiated. Monitor the patient closely until the oncologist responds."
    2. Actionable Tasks: "1. Stay physically present with the patient at all times. 2. Prepare ID and medical documents for the arriving physician."
    3. Emotional Navigation: [Provide 1 empathetic phrase acknowledging the high stress of the emergency situation].

    RULE 1 — ISSUE FILTER: You MUST ONLY provide advice that directly matches the specific 
    "Issues" listed in the User Query. Any topic present in the Context but NOT listed in 
    Issues must be completely ignored.

    RULE 2 — EMPTY ISSUES HANDLER: If Issues = "NO SPECIFIC ISSUES REPORTED", output:
    "1. Red Flags: No specific concerns flagged. Continue standard observation protocol.
     2. Actionable Tasks: N/A — no issues reported by patient.
     3. Emotional Navigation: [one empathetic sentence from context only]"
    You are FORBIDDEN from using base medical knowledge for Red Flags or Actionable Tasks 
    when no issues are reported.

    RULE 3 — RELEVANCE CHECK (MANDATORY): Before writing each section, verify that the 
    Context explicitly mentions each reported Issue by keyword or close synonym. If the 
    Context does NOT explicitly address a reported Issue — treat it as missing information 
    regardless of whether the context is empty or contains other topics. For each unaddressed 
    issue output EXACTLY: "I cannot find information about [ISSUE] in the IKNL databases. 
    Please consult your doctor." NEVER substitute with internal medical knowledge.

    RULE 4 — FORMAT EXCEPTION: Use the 3-section format ONLY when the context explicitly 
    addresses ALL reported issues. If Rule 3 triggers for ANY issue, output ONLY the fallback 
    message(s) — NO section headers, NO 3-section structure.

    Answer in English. Format EXACTLY in 3 sections (unless Rules 0, 2, or 4 apply):
    1. Red Flags: 1-2 critical symptoms based ONLY on the context.
    2. Actionable Tasks: 2 practical steps based ONLY on the context.
    3. Emotional Navigation: 1 empathetic phrase, no toxic positivity.

    Context:
    {context}

    User Query (Distress Score & Issues):
    {input}
    """
    prompt = PromptTemplate.from_template(template)
    
    # Берем больше чанков, чтобы не пропустить инфу, если выбрано сразу 3 проблемы
    retriever = vector_db.as_retriever(search_kwargs={"k": 4})
    
    # Исправленный синтаксис LCEL
    chain = (
        {"context": retriever | format_docs, "input": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    class RAGWrapper:
        def invoke(self, query_dict):
            user_text = query_dict["input"]
            answer = chain.invoke(user_text)
            return {"answer": answer}
            
    return RAGWrapper()