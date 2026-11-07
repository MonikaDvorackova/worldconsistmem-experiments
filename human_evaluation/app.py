"""Blind human annotation interface for WorldConsistMem."""
import csv
import io
import json
import os
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="WorldConsistMem | Human Evaluation", layout="centered")
st.title("WorldConsistMem — nezávislé hodnocení")
st.caption("Posuzujte věcnou správnost podle důkazů; samotný formát JSON nehodnoťte.")

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
if not path.is_file():
    st.error("Dataset zatím nebyl nahrán správcem. Hodnocení není dostupné.")
    st.stop()

@st.cache_data
def read_rows():
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

rows = read_rows()
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
done = sum(bool(ratings.get(r["response_id"], {}).get("semantic_correct")) and bool(ratings.get(r["response_id"], {}).get("evidence_sufficient")) for r in rows)
st.progress(done / len(rows), text=f"Vyplněno {done}/{len(rows)}")
idx = st.session_state.idx
row = rows[idx]
rid = row["response_id"]
current = ratings.get(rid, {})
st.subheader(f"Odpověď {idx+1} z {len(rows)}")
st.caption(f"Případ {row['case_id']} · {rid}")
st.markdown("**Otázka**")
st.write(row["question"])
with st.expander("Důkazy", expanded=True):
    try:
        st.json(json.loads(row["evidence_json"]))
    except (TypeError, ValueError):
        st.code(row["evidence_json"])
st.markdown("**Odpověď modelu**")
try:
    st.json(json.loads(row["raw_model_response"]))
except (TypeError, ValueError):
    st.code(row["raw_model_response"])

correct_options = ["correct","incorrect","ambiguous"]
suff_options = ["yes","no","unclear"]
with st.form(f"evaluation_{rid}"):
    correct = st.radio("Je odpověď věcně správná?", correct_options,
        index=correct_options.index(current["semantic_correct"]) if current.get("semantic_correct") in correct_options else None,
        format_func=lambda x: {"correct":"Správná","incorrect":"Nesprávná","ambiguous":"Nelze určit"}[x])
    suff = st.radio("Jsou důkazy dostatečné?", suff_options,
        index=suff_options.index(current["evidence_sufficient"]) if current.get("evidence_sufficient") in suff_options else None,
        format_func=lambda x: {"yes":"Ano","no":"Ne","unclear":"Nelze určit"}[x])
    notes = st.text_area("Poznámka (povinná při nesprávném nebo nejednoznačném hodnocení)", value=current.get("notes",""))
    left, right = st.columns(2)
    prev = left.form_submit_button("Uložit a předchozí", disabled=idx == 0)
    nxt = right.form_submit_button("Uložit a další", disabled=idx == len(rows)-1)
    save = st.form_submit_button("Uložit hodnocení")
    if prev or nxt or save:
        if correct is None or suff is None:
            st.error("Vyplňte obě hodnocení.")
        elif correct in ("incorrect","ambiguous") and not notes.strip():
            st.error("Doplňte důvod hodnocení.")
        else:
            ratings[rid] = {"semantic_correct":correct,"evidence_sufficient":suff,"notes":notes.strip()}
            if prev: st.session_state.idx -= 1
            if nxt: st.session_state.idx += 1
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
