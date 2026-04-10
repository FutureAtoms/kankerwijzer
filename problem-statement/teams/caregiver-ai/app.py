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
import streamlit as st
import time
import glob
from rag_engine import build_vector_db, get_rag_chain
from datetime import datetime

# --- НАСТРОЙКА ---
st.set_page_config(page_title="Family OS | IKNL", page_icon="🎗️", layout="wide")

@st.cache_resource(show_spinner=False)
def init_rag():
    pdf_files = glob.glob("data/*.pdf")
    if not pdf_files:
        return None
    db = build_vector_db(pdf_files)
    return get_rag_chain(db)

# Инициализация переменных состояния сессии (FIX: State Management)
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'ai_response' not in st.session_state: st.session_state.ai_response = ""
if 'audit_log' not in st.session_state: st.session_state.audit_log = []
if 'lastmeter_score' not in st.session_state: st.session_state.lastmeter_score = 0
if 'is_decrypted' not in st.session_state: st.session_state.is_decrypted = False
# FIX B8: Динамические счетчики для Tab 3
if 'metric_missing' not in st.session_state: st.session_state.metric_missing = 14
if 'metric_helpful' not in st.session_state: st.session_state.metric_helpful = 89
# ДОБАВЛЕНО: Динамический счетчик петель опекуна
if 'partner_loops' not in st.session_state: st.session_state.partner_loops = 1240

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.title("System Settings")
st.sidebar.markdown("---")
privacy_filter = st.sidebar.toggle("🔒 FCS Privacy Filter >>>", value=True)
patient_name = "[PATIENT_ID_847]" if privacy_filter else "Anna Smith (DOB: 1985)"

st.sidebar.markdown("### Infrastructure Status")
st.sidebar.success("✅ Connected to Patient's Solid Pod")
st.sidebar.success("✅ HL7 FHIR Mapping: Active")
st.sidebar.info("FCS 0.1: Zero-Data Retention.")

# --- Вкладки (Tabs) ---
tab_patient, tab_caregiver, tab_clinic = st.tabs([
    "👤 Patient View (Lastmeter 2.0)", 
    "📱 Caregiver View (Partner Loop)", 
    "🏥 IKNL & Clinic Dashboard"
])

# ==========================================
# ТАБ 1: PATIENT VIEW
# ==========================================
with tab_patient:
    st.title("Family OS: Digitized Lastmeter")
    st.markdown(f"**Current Patient:** {patient_name}")
    
    with st.container(border=True):
        st.subheader("1. Distress Level")
        # FIX B5: Отвязываем прямой байнд к session_state, чтобы не перезаписывать при reruns
        current_slider_val = st.slider("How much distress have you been experiencing this past week?", 0, 10, 2)
        
        st.subheader("2. Current Challenges")
        col1, col2, col3 = st.columns(3)
        with col1: issue_childcare = st.checkbox("Childcare")
        with col2: issue_work = st.checkbox("Work / Finances")
        with col3: issue_fatigue = st.checkbox("Severe Fatigue")
        
        st.markdown("---")
        liquid_consent = st.checkbox("Liquid Consent: Automatically send instructions to my partner if distress is > 4.", value=True)

    if st.button("Submit Assessment", type="primary"):
        st.session_state.lastmeter_score = current_slider_val
        st.session_state.is_decrypted = False 
        
        issues = []
        if issue_childcare: issues.append("childcare")
        if issue_work: issues.append("work and finances")
        if issue_fatigue: issues.append("severe fatigue")
        issues_text = ", ".join(issues) if issues else "NO SPECIFIC ISSUES REPORTED"
        
        current_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.audit_log.append(f"{current_time} - Patient submitted Lastmeter (Score: {st.session_state.lastmeter_score})")

        # 1. Генерируем ответ ИИ (если Зеленая Зона ИЛИ включен Liquid Consent)
        if st.session_state.lastmeter_score <= 3 or liquid_consent:
            rag_chain = init_rag()
            if not rag_chain:
                st.warning("⚠️ Пожалуйста, положите PDF файлы в папку 'data'.")
            else:
                with st.spinner("Connecting fragmented sources (IKNL, Kanker.nl)..."):
                    time.sleep(1) 
                    query = f"Patient Distress Score: {st.session_state.lastmeter_score}. Issues: {issues_text}."
                    response = rag_chain.invoke({"input": query})
                    
                    st.session_state.ai_response = response["answer"]
                    st.session_state.analysis_done = True
                    log_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.audit_log.append(f"{log_time} - AI generated Caregiver checklist")

        # 2. Отрисовываем ПРАВИЛЬНЫЙ интерфейс в зависимости от оценки
        if st.session_state.lastmeter_score >= 4:
            # КРАСНАЯ ЗОНА: Строгий интерфейс без зеленых галочек
            st.error("🔴 Red Zone. AI Medical Advice blocked. Escalating to human oncologist immediately.")
            if liquid_consent:
                st.info("ℹ️ Liquid Consent Active: Non-medical logistical tasks routed to Caregiver's phone.")
            else:
                st.session_state.analysis_done = False
                st.warning("🔒 Caregiver loop blocked (Consent not granted).")
        else:
            # ЗЕЛЕНАЯ ЗОНА: Позитивный интерфейс
            st.info("Sources Connected: [Richtlijnendatabase] + [Kanker.nl]")
            st.success("🟢 Assessment processed. Actionable tasks securely routed to Caregiver's phone.")

    if st.session_state.audit_log:
        with st.expander("Audit Trail (Access Log)", expanded=True):
            for log in st.session_state.audit_log:
                st.code(log)

# ==========================================
# ТАБ 2: CAREGIVER VIEW (WOW FACTOR)
# ==========================================
with tab_caregiver:
    st.markdown("<div style='text-align: center;'><h3>📱 Partner's Phone</h3></div>", unsafe_allow_html=True)
    
    if not st.session_state.analysis_done:
        st.info("Waiting for patient assessment or consent...")
    else:
        with st.container(border=True):
            st.warning("🔒 New Actionable Checklist generated based on patient's Lastmeter score.")
            
            # FIX B4: Управление состоянием расшифровки
            if not st.session_state.is_decrypted:
                if st.button("Decrypt Data (Partner Loop Authorization)"):
                    with st.spinner("Verifying cryptographic WebID & REBAC policies..."):
                        time.sleep(2) 
                        log_time = datetime.now().strftime("%H:%M:%S")
                        st.session_state.audit_log.append(f"{log_time} - Partner [ID] decrypted instruction")
                        st.session_state.is_decrypted = True
                        
                        # ДОБАВЛЕНО: Увеличиваем счетчик петель опекуна при успешной расшифровке
                        st.session_state.partner_loops += 1
                        
                        st.rerun() # Мгновенная перезагрузка для отображения контента
            
            # Контент показывается по сохраненному флагу, чекбоксы его больше не сбрасывают
            if st.session_state.is_decrypted:
                st.success("Authorization Successful.")
                st.markdown("### AI Navigation Protocol")
                st.markdown(st.session_state.ai_response)
                
                st.markdown("---")
                st.markdown("### 📋 Caregiver Action Tracker")
                st.caption("Checking these boxes generates Caregiver-Reported Outcomes (CROs) for the clinic.")
                c1 = st.checkbox("Task 1 Completed (Logistics/Care)")
                c2 = st.checkbox("Task 2 Completed (Emotional Navigation)")
                
                if c1 or c2:
                    st.toast("✅ CRO Data synced with National Cancer Registry!", icon="🔄")

                st.markdown("---")
                st.markdown("**Was this information helpful?**")
                fb_col1, fb_col2 = st.columns(2)
                with fb_col1: 
                    if st.button("👍 Clear"):
                        st.session_state.metric_helpful += 1
                        st.toast("Feedback recorded!")
                with fb_col2: 
                    if st.button("👎 Missing/Unclear"):
                        st.session_state.metric_missing += 1
                        st.toast("Flagged for IKNL Content Team.", icon="⚠️")

# ==========================================
# ТАБ 3: IKNL & CLINIC DASHBOARD
# ==========================================
with tab_clinic:
    st.title("IKNL Data Insights & Clinic Alerts")

    st.markdown("#### 📚 Knowledge Base Feedback Loop")
    st.caption("Aggregated anonymized feedback to improve IKNL guidelines.")
    col1, col2, col3 = st.columns(3)
    
    # ДОБАВЛЕНО: Динамический вывод счетчика с запятой для тысяч (например, 1,241)
    col1.metric("Active Caregiver Loops", f"{st.session_state.partner_loops:,}", "+12% this week")
    
    # FIX B8: Метрики теперь динамические!
    col2.metric("Helpful Ratings", f"{st.session_state.metric_helpful}%", "+1% (session)")
    col3.metric("Missing Info Flags", str(st.session_state.metric_missing), "Requires IKNL review", delta_color="inverse")

    st.info("⚠️ **Top Missing Topic today:** 'Interaction between new drug X and grapefruit'. Sent to IKNL Content Team.")
    st.divider()

    st.markdown("#### 🚨 Clinical Triage (Red Zone Alerts)")
    
    # FIX B2: Независимый красный алерт
    if st.session_state.lastmeter_score > 3:
        st.error(f"🔴 **URGENT ALERT: Patient {patient_name}**\n\n"
                 f"Lastmeter Score: **{st.session_state.lastmeter_score}** (Severe Distress).\n\n"
                 "*Action taken:* Alert routed to Oncologist on duty.")
    else:
        st.success(f"🟢 **Status Normal:** Patient {patient_name} is in the Green Zone (Score: {st.session_state.lastmeter_score}). Caregiver Loop active.")