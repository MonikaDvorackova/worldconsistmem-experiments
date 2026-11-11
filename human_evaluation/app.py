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
st.caption(f"Případ {row['case_id']} · {rid} · Každou odpověď posuzujte samostatně.")

def readable(value):
    if value is None: return "neuvedeno"
    if isinstance(value, bool): return "ano" if value else "ne"
    if isinstance(value, (dict, list)): return json.dumps(value, ensure_ascii=False)
    return str(value)

EVENT_NAMES = {
    "role_replacement": "Výměna osoby v roli",
    "role_assignment": "Přiřazení osoby k roli",
    "conflict_introduction": "Vznik konfliktu",
    "conflict_resolution": "Vyřešení konfliktu",
    "document_revision": "Revize dokumentu",
    "ownership_transfer": "Převod vlastnictví",
}
FIELD_NAMES = {
    "org_id": "Organizace", "role": "Role", "person_id": "Osoba",
    "old_person_id": "Původní osoba", "new_person_id": "Nová osoba",
    "conflict_id": "Konflikt", "document_id": "Dokument",
    "project_id": "Projekt", "old_owner_id": "Původní vlastník",
    "new_owner_id": "Nový vlastník", "from_version": "Původní verze",
    "to_version": "Nová verze", "exclusive": "Výhradní přiřazení",
}
def render_evidence(raw):
    try:
        evidence = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        st.warning("Podklady nelze přečíst; zvolte Nelze posoudit.")
        return
    if not isinstance(evidence, list):
        st.write(evidence)
        return
    st.caption("Čas je pořadové číslo události, nikoli datum. Každý řádek je samostatná událost.")
    def order(item):
        t = item.get("t", item.get("s", {}).get("t")) if isinstance(item, dict) else None
        return (0, t) if isinstance(t, (int, float)) and not isinstance(t, bool) else (1, str(t))
    for event in sorted(evidence, key=order):
        if not isinstance(event, dict):
            st.write(readable(event))
            continue
        source = event.get("s") if isinstance(event.get("s"), dict) else {}
        props = source.get("p") if isinstance(source.get("p"), dict) else {}
        time = source.get("t", event.get("t", "?"))
        kind = source.get("et", "Neznámá událost")
        description = " · ".join(f"{FIELD_NAMES.get(k, k)}: {readable(v)}" for k, v in props.items())
        st.markdown(f"**Čas {time} — {EVENT_NAMES.get(kind, kind)}**")
        if description:
            st.write(description)
    with st.expander("Technické podklady (JSON)"):
        st.json(evidence)

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

st.markdown("### 1. Co se ptáme?")
st.write(row["question"])
st.markdown("### 2. Co ukazují podklady?")
render_evidence(row["evidence_json"])
st.markdown("### 3. Co odpověděl model?")
render_model_answer(row["raw_model_response"])
st.markdown("### 4. Je odpověď správná?")
st.caption("Správně = odpověď odpovídá doloženým událostem. Špatně = události jí odporují. Nelze posoudit = více možných časů, chybějící souvislost nebo nejasná otázka. Není potřeba hádat. Posuzujte význam odpovědi, ne JSON formát.")

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
