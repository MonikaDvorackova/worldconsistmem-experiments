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
st.title("Nezávislé hodnocení")
st.write("Vyberte hodnocení odpovědi a pokračujte. Bez povinného odůvodnění.")
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

round_choice = "Round 2 — sporné odpovědi"
reviewer_choice = st.selectbox("Hodnotitel", ["reviewer_1", "reviewer_2"])
round_two = round_choice.startswith("Round 2")
if round_two:
    packet_path = Path(__file__).parent / "round_2" / reviewer_choice / "BLIND_REVIEW_PACKET.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    rows = [{**item, "evidence_json": json.dumps(item["evidence_json"], ensure_ascii=False)} for item in packet]
    st.caption("Druhé kolo · 50 sporných odpovědí · původní hodnocení je skryté.")
else:
    path = Path(__file__).resolve().parent.parent / "BLINDED_ANNOTATION.csv"
if not round_two and path.is_file():
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
elif not round_two:
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

dataset_key = (round_two, reviewer_choice)
if st.session_state.get("dataset_key") != dataset_key:
    st.session_state.dataset_key = dataset_key
    st.session_state.ratings = {}
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
done = sum(bool(ratings.get(r["response_id"], {}).get("semantic_correct")) for r in rows)
st.progress(done / len(rows), text=f"Vyplněno {done}/{len(rows)}")
idx = st.session_state.idx
row = rows[idx]
rid = row["response_id"]
current = ratings.get(rid, {})
st.subheader(f"Hodnocení {idx+1} / {len(rows)}")
st.caption(f"Případ {row['case_id']} · {rid}")

def readable(value):
    if value is None: return "neuvedeno"
    if isinstance(value, bool): return "ano" if value else "ne"
    if isinstance(value, (dict, list)): return json.dumps(value, ensure_ascii=False)
    return str(value)

def render_evidence(raw):
    try: evidence = json.loads(raw)
    except (ValueError, TypeError):
        st.warning("Důkazy nelze strukturovaně zobrazit.")
        st.code(raw)
        return
    if not isinstance(evidence, list):
        st.json(evidence)
        return
    events = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            st.write(readable(item))
            continue
        source = item.get("s") if isinstance(item.get("s"), dict) else {}
        props = source.get("p") if isinstance(source.get("p"), dict) else {}
        time = source.get("t", item.get("t"))
        events.append((time, index, item, source, props))
    def sort_key(entry):
        time = entry[0]
        return (0, time, entry[1]) if isinstance(time, (int, float)) and not isinstance(time, bool) else (1, str(time), entry[1])
    st.caption("Seřazeno chronologicky podle t. Časový krok není kalendářní datum.")
    for time, _, item, source, props in sorted(events, key=sort_key):
        with st.container(border=True):
            st.markdown(f"**Čas {readable(time)}** · Událost: `{readable(source.get('et'))}`")
            for key, value in props.items():
                st.write(f"**{key}:** {readable(value)}")
            if item.get("id"): st.caption(f"Zdrojový záznam: {item['id']}")
    st.info("Samotná chronologie neprokazuje, která revize je přechod v1 → v2. Neodvozujte verze pouze z čísel v identifikátorech.")

def render_model_answer(raw):
    try: response = json.loads(raw)
    except (ValueError, TypeError):
        st.write(raw)
        return
    if isinstance(response, dict):
        if response.get("abstain") is True: st.info("Model se zdržel odpovědi.")
        answer = response.get("answer", response)
        if isinstance(answer, dict):
            for key, value in answer.items(): st.write(f"**{key}:** {readable(value)}")
        else: st.write(readable(answer))
        if response.get("provenance") is not None: st.caption(f"Odkazovaný důkaz: {readable(response['provenance'])}")
    else: st.write(readable(response))
    with st.expander("Původní odpověď (JSON)"): st.json(response)

st.markdown("**Otázka**")
st.write(row["question"])
with st.expander("Podklady k ověření odpovědi", expanded=False):
    render_evidence(row["evidence_json"])
st.markdown("**Odpověď modelu**")
render_model_answer(row["raw_model_response"])

with st.form(f"evaluation_{rid}"):
    options = ["correct", "incorrect", "ambiguous"]
    selected = st.radio(
        "Hodnocení",
        options,
        index=options.index(current["semantic_correct"]) if current.get("semantic_correct") in options else None,
        format_func=lambda value: {
            "correct": "Správně",
            "incorrect": "Špatně",
            "ambiguous": "Nelze posoudit",
        }[value],
        horizontal=True,
    )
    left, right = st.columns(2)
    previous = left.form_submit_button("← Předchozí", disabled=idx == 0)
    next_item = right.form_submit_button("Uložit a další →", type="primary")
    if previous:
        st.session_state.idx -= 1
        st.rerun()
    if next_item:
        if selected is None:
            st.error("Vyberte jednu ze tří možností.")
        else:
            ratings[rid] = {
                "semantic_correct": selected,
                "evidence_sufficient": "unclear",
                "notes": "",
                "rubric_reason": "",
            }
            if idx < len(rows) - 1:
                st.session_state.idx += 1
            st.rerun()

st.download_button("Stáhnout průběžnou zálohu", json.dumps(ratings,ensure_ascii=False,indent=2),
                   file_name=f"wcm_round_{2 if round_two else 1}_{reviewer_choice}_progress.json", mime="application/json")
if done == len(rows):
    output = io.StringIO()
    columns = list(rows[0].keys())
    for c in ("semantic_correct","evidence_sufficient","notes","rubric_reason"):
        if c not in columns: columns.append(c)
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        writer.writerow({**r, **ratings[r["response_id"]]})
    st.success("Všechna hodnocení jsou vyplněna.")
    st.download_button("Stáhnout dokončené CSV", output.getvalue().encode("utf-8-sig"),
                       file_name=f"WCM_round_{2 if round_two else 1}_{reviewer_choice}_COMPLETED.csv", mime="text/csv")
