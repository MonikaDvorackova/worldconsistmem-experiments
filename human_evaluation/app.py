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
st.progress(done / len(rows), text=f"Vyplněno {done}/{len(rows)}")
idx = st.session_state.idx
row = rows[idx]
rid = row["response_id"]
current = ratings.get(rid, {})
st.subheader(f"Kontrola odpovědi {idx+1} / {len(rows)}")

def format_answer(raw):
    try:
        response = json.loads(raw)
    except (ValueError, TypeError):
        return str(raw)
    if isinstance(response, dict):
        if response.get("abstain") is True:
            return "Model neodpověděl."
        answer = response.get("answer", response)
        if isinstance(answer, dict):
            if "t" in answer:
                return f"Čas {answer['t']}"
            return ", ".join(f"{k}: {v}" for k, v in answer.items())
        if isinstance(answer, (int, float)) and not isinstance(answer, bool):
            return f"Čas {answer}"
        return str(answer)
    return str(response)

def concise_evidence(raw):
    try:
        evidence = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(evidence, list):
        return None
    events = []
    for item in evidence:
        if not isinstance(item, dict):
            return None
        source = item.get("s")
        if not isinstance(source, dict):
            return None
        t = source.get("t", item.get("t"))
        if t is None:
            return None
        events.append((t, source.get("et", "událost")))
    return events

st.markdown("**Otázka**")
st.write(row["question"])
st.markdown("**Odpověď modelu**")
st.markdown(f"### {format_answer(row['raw_model_response'])}")
st.markdown("**Podklady k ověření**")
events = concise_evidence(row["evidence_json"])
if events is not None:
    st.write("Zaznamenané události (časový krok — typ):")
    for time, event_type in sorted(events, key=lambda e: (str(type(e[0])), e[0])):
        st.write(f"**{time}** — {event_type}")
else:
    st.warning("Podklady nejsou ve standardním formátu. Otevřete technické detaily.")
st.caption("Záznamy samy nemusí dokazovat, která událost odpovídá konkrétní verzi. V takovém případě vyberte Nevím.")
with st.expander("Technické detaily (nepovinné)"):
    st.caption(f"Případ {row['case_id']} · {rid}")
    st.write("Původní otázka:", row["question"])
    st.write("Původní odpověď:")
    try:
        st.json(json.loads(row["raw_model_response"]))
    except (ValueError, TypeError):
        st.code(row["raw_model_response"])
    st.write("Původní důkazy:")
    try:
        st.json(json.loads(row["evidence_json"]))
    except (ValueError, TypeError):
        st.code(row["evidence_json"])

choices = {"correct": "Ano", "incorrect": "Ne", "ambiguous": "Nevím"}
with st.form(f"evaluation_{rid}"):
    correct = st.radio(
        "Lze odpověď potvrdit podle podkladů?",
        list(choices),
        index=list(choices).index(current["semantic_correct"]) if current.get("semantic_correct") in choices else None,
        format_func=lambda value: choices[value],
        horizontal=True,
    )
    left, right = st.columns(2)
    prev = left.form_submit_button("Předchozí", disabled=idx == 0)
    nxt = right.form_submit_button("Uložit a pokračovat", disabled=idx == len(rows)-1)
    save = st.form_submit_button("Uložit", disabled=False)
    if prev or nxt or save:
        if correct is None and not prev:
            st.error("Vyberte Ano, Ne nebo Nevím.")
        else:
            if correct is not None:
                # Retain legacy export schema; evidence sufficiency is not inferred.
                ratings[rid] = {
                    "semantic_correct": correct,
                    "evidence_sufficient": "",
                    "notes": current.get("notes", ""),
                }
            if prev:
                st.session_state.idx -= 1
            elif nxt:
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
