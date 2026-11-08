"""Blind human annotation interface for WorldConsistMem."""
import csv
import io
import json
import os
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="WorldConsistMem | Human Evaluation", layout="centered", page_icon="◈")
style_path = Path(__file__).parent / "style.css"
if style_path.exists():
    st.markdown("<style>" + style_path.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
st.caption("WORLD CONSIST MEM  /  HUMAN EVALUATION")
st.title("Kontrola odpovědí")
st.write("Přečtěte otázku a odpověď modelu. Podle podkladů vyberte Ano, Ne nebo Nevím.")
st.divider()

code = os.environ.get("WCM_ACCESS_CODE", "")
if not code:
    st.error("Správce musí nastavit WCM_ACCESS_CODE v tajných proměnných hostingu.")
    st.stop()
if "authorized" not in st.session_state:
    st.session_state.authorized = False
if not st.session_state.authorized:
    entered = st.text_input("Přístupový kód", type="password")
    if st.button("Přihlásit"):
        import hmac
        st.session_state.authorized = hmac.compare_digest(entered, code)
        if st.session_state.authorized:
            st.rerun()
    st.stop()

path = Path(__file__).resolve().parent.parent / "BLINDED_ANNOTATION.csv"
if path.is_file():
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
else:
    st.info("Dataset ještě není uložen na serveru. Můžete jej načíst přímo z CSV souboru.")
    uploaded_dataset = st.file_uploader(
        "Vyberte BLINDED_ANNOTATION.csv", type=["csv"], key="dataset_upload",
        help="Soubor zůstane pouze v aktuální relaci. Pro trvalý přístup hodnotitelů jej správce musí nasadit na server."
    )
    if uploaded_dataset is None:
        st.stop()
    try:
        rows = list(csv.DictReader(io.StringIO(uploaded_dataset.getvalue().decode("utf-8-sig"))))
    except UnicodeDecodeError:
        st.error("CSV musí být kódované v UTF-8.")
        st.stop()
    st.warning("Dočasné načtení: po obnovení nebo ukončení relace může být nutné CSV nahrát znovu. Hodnocení pravidelně zálohujte.")
required = {"case_id","response_id","question","evidence_json","raw_model_response"}
if not rows or any(not required.issubset(row) for row in rows):
    st.error("Dataset nemá požadované sloupce.")
    st.stop()
if len({r["response_id"] for r in rows}) != len(rows):
    st.error("Duplicitní response_id.")
    st.stop()

if "ratings" not in st.session_state:
    st.session_state.ratings = {}
if "idx" not in st.session_state:
    st.session_state.idx = 0

with st.expander("Obnovit rozpracované hodnocení"):
    uploaded = st.file_uploader("Soubor průběhu (JSON)", type="json")
    if uploaded and st.button("Obnovit"):
        try:
            data = json.load(uploaded)
            ids = {r["response_id"] for r in rows}
            assert isinstance(data, dict) and set(data).issubset(ids)
            assert all(isinstance(v, dict) for v in data.values())
            st.session_state.ratings = data
            st.success("Obnoveno.")
        except (ValueError, AssertionError, json.JSONDecodeError):
            st.error("Neplatný soubor průběhu.")

ratings = st.session_state.ratings
done = sum(ratings.get(r["response_id"], {}).get("semantic_correct") in ("correct", "incorrect", "ambiguous") for r in rows)
st.progress(done / len(rows), text=f"Vyplněno {done}/{len(rows)} odpovědí")

# One case is shown once, with all its blinded candidate responses.
cases = {}
for record in rows:
    cases.setdefault(record["case_id"], []).append(record)
case_ids = list(cases)
st.session_state.idx = min(st.session_state.idx, len(case_ids) - 1)
idx = st.session_state.idx
case_id = case_ids[idx]
case_rows = cases[case_id]
reference = case_rows[0]
st.subheader(f"Případ {idx+1} / {len(case_ids)}")
st.caption(f"{len(case_rows)} odpovědi ke stejné otázce")

import re

def plain_question(question):
    match = re.fullmatch(r"When was .+ revised from v1 to v2\\?", question)
    if match:
        return "Kdy byl dokument změněn z verze 1 na verzi 2?"
    match = re.fullmatch(r"When and how did the CEO of .+ change\\?", question)
    if match:
        return "Kdy a jak se změnil generální ředitel organizace?"
    return question

def answer_summary(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return str(raw)
    if isinstance(value, dict):
        if value.get("abstain") is True:
            return "Model neodpověděl."
        answer = value.get("answer", value)
        if isinstance(answer, dict):
            return " · ".join(f"{k}: {v}" for k, v in answer.items())
        return str(answer)
    return str(value)

st.markdown("**Otázka**")
st.write(plain_question(reference["question"]))
st.markdown("**Co víme z podkladů**")
try:
    evidence = json.loads(reference["evidence_json"])
except (ValueError, TypeError):
    evidence = None
if isinstance(evidence, list):
    event_lines = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = item.get("s", {})
        if not isinstance(source, dict):
            continue
        t = source.get("t", item.get("t"))
        event_type = source.get("et", "událost")
        event_lines.append((t, event_type))
    for t, event_type in sorted(event_lines, key=lambda x: str(x[0]).zfill(12)):
        st.write(f"Čas **{t}** — {event_type}")
else:
    st.warning("Podklady nemají standardní strukturu.")
st.caption("Samotný seznam revizí nemusí určovat, která znamená přechod mezi verzemi. Pokud nelze odpověď ověřit, zvolte Nevím.")
with st.expander("Technické podklady (nepovinné)"):
    st.write(reference["question"])
    st.json(evidence) if evidence is not None else st.code(reference["evidence_json"])

st.markdown("### Posuďte jednotlivé odpovědi")
st.caption("Ano = podklady potvrzují. Ne = podklady vyvracejí. Nevím = nelze rozhodnout. Každá volba se ihned uloží do průběhu této relace.")
for position, record in enumerate(case_rows, start=1):
    rid = record["response_id"]
    selected = ratings.get(rid, {}).get("semantic_correct")
    with st.container(border=True):
        st.markdown(f"**Odpověď {position}:** {answer_summary(record['raw_model_response'])}")
        if selected in ("correct", "incorrect", "ambiguous"):
            st.caption("Zvoleno: " + {"correct": "Ano", "incorrect": "Ne", "ambiguous": "Nevím"}[selected])
        cols = st.columns(3)
        for col, key, label in zip(cols, ("correct", "incorrect", "ambiguous"), ("Ano", "Ne", "Nevím")):
            if col.button(label, key=f"rate_{rid}_{key}", use_container_width=True, type="primary" if selected == key else "secondary"):
                ratings[rid] = {"semantic_correct": key, "evidence_sufficient": "", "notes": ""}
                st.rerun()
        with st.expander("Původní odpověď (nepovinné)"):
            try:
                st.json(json.loads(record["raw_model_response"]))
            except (ValueError, TypeError):
                st.code(record["raw_model_response"])

previous, following = st.columns(2)
if previous.button("Předchozí případ", disabled=idx == 0, use_container_width=True):
    st.session_state.idx -= 1
    st.rerun()
if following.button("Další případ", disabled=idx == len(case_ids)-1, use_container_width=True):
    st.session_state.idx += 1
    st.rerun()

st.download_button("Stáhnout průběžnou zálohu", json.dumps(ratings,ensure_ascii=False,indent=2),
                   file_name="wcm_annotation_progress.json", mime="application/json")
if done == len(rows):
    output = io.StringIO()
    columns = list(rows[0].keys())
    for c in ("semantic_correct","evidence_sufficient","notes"):
        if c not in columns: columns.append(c)
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        writer.writerow({**r, **ratings[r["response_id"]]})
    st.success("Všechna hodnocení jsou vyplněna.")
    st.download_button("Stáhnout dokončené CSV", output.getvalue().encode("utf-8-sig"),
                       file_name="WCM_COMPLETED_ANNOTATION.csv", mime="text/csv")
