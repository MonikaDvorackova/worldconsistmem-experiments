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
st.write("Porovnejte odpovědi modelu s jednoduše popsanou skutečností. Vyberte Správně, Špatně nebo Nelze posoudit.")
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

def describe_case(question):
    patterns = [
        (r"When was (.+) revised from v1 to v2\?", "Kdy byl dokument změněn z verze 1 na verzi 2?", "document_revision"),
        (r"When and how did the CEO of (.+) change\?", "Kdy a jak se změnil generální ředitel organizace?", "role_replacement"),
        (r"When did (.+) leave (.+)\?", "Kdy zaměstnanec opustil organizaci?", "person_leaves_org"),
        (r"When was conflict (.+) resolved\?", "Kdy byl vyřešen spor?", "conflict_resolution"),
        (r"When did ownership of (.+) transfer\?", "Kdy byl projekt převeden na jinou organizaci?", "project_ownership_transfer"),
    ]
    for pattern, label, event_type in patterns:
        match = re.fullmatch(pattern, question)
        if match:
            return label, event_type, match.groups()
    return question, None, ()

def reference_fact(question):
    label, event_type, identifiers = describe_case(question)
    if not event_type:
        return label, None, "Neznámý typ otázky"
    world_id = identifiers[0].split(":")[0]
    world_path = Path(__file__).resolve().parent.parent / "data" / "scaled" / "worlds" / (world_id + ".json")
    if not world_path.is_file():
        return label, None, "Chybí referenční svět"
    try:
        world = json.loads(world_path.read_text(encoding="utf-8"))
        events = world["events"]
    except (ValueError, KeyError, OSError):
        return label, None, "Referenční svět nelze načíst"
    matched = []
    for event in events:
        if event.get("event_type") != event_type:
            continue
        p = event.get("payload", {})
        if event_type == "document_revision":
            ok = p.get("base_doc_id") == identifiers[0] and p.get("expected_prev_version") == 1
        elif event_type == "role_replacement":
            ok = p.get("org_id") == identifiers[0] and p.get("role") == "CEO"
        elif event_type == "person_leaves_org":
            ok = p.get("person_id") == identifiers[0] and p.get("org_id") == identifiers[1]
        elif event_type == "conflict_resolution":
            ok = p.get("conflict_id") == identifiers[0]
        else:
            ok = p.get("project_id") == identifiers[0]
        if ok:
            matched.append(event)
    if not matched:
        return label, None, "Odpovídající událost nebyla nalezena"
    # A changing world may legitimately have several matching transitions.
    # Show the full timeline rather than falsely claiming that no reference exists.
    if len(matched) > 1:
        facts = []
        for event in sorted(matched, key=lambda e: e.get("t", 0)):
            p = event.get("payload", {})
            t = event.get("t")
            if event_type == "role_replacement":
                facts.append(f"V čase {t} byl ředitel nahrazen: osoba {str(p.get('old_person_id', '?')).split(':')[-1]} → osoba {str(p.get('new_person_id', '?')).split(':')[-1]}.")
            elif event_type == "project_ownership_transfer":
                facts.append(f"V čase {t} byl projekt převeden: organizace {str(p.get('old_org_id', '?')).split(':')[-1]} → organizace {str(p.get('new_org_id', '?')).split(':')[-1]}.")
            elif event_type == "document_revision":
                facts.append(f"V čase {t} proběhla revize dokumentu.")
            else:
                facts.append(f"V čase {t} nastala odpovídající událost.")
        return label, " ".join(facts), None
    event = matched[0]
    p = event.get("payload", {})
    t = event.get("t")
    if not isinstance(t, int):
        return label, None, "Chybí čas události"
    if event_type == "document_revision":
        fact = f"Dokument přešel z verze 1 na verzi 2 v čase {t}."
    elif event_type == "role_replacement":
        fact = f"V čase {t} byl generální ředitel nahrazen. Původní osoba: {p.get('old_person_id', '?').split(':')[-1]}; nová osoba: {p.get('new_person_id', '?').split(':')[-1]}."
    elif event_type == "person_leaves_org":
        fact = f"Zaměstnanec opustil organizaci v čase {t}."
    elif event_type == "conflict_resolution":
        fact = f"Spor byl vyřešen v čase {t}. Výsledek: {p.get('resolved_value', 'neuveden')}."
    else:
        fact = f"Projekt byl převeden v čase {t}. Původní organizace: {p.get('old_org_id', '?').split(':')[-1]}; nová organizace: {p.get('new_org_id', '?').split(':')[-1]}."
    return label, fact, None

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
            time = answer.get("t", answer.get("time"))
            details = []
            if time is not None:
                details.append(f"Čas {time}")
            for key, name in (("old_person_id", "Původní osoba"), ("new_person_id", "Nová osoba"), ("old_org_id", "Původní organizace"), ("new_org_id", "Nová organizace"), ("resolved_value", "Výsledek")):
                if key in answer:
                    details.append(f"{name}: {str(answer[key]).split(':')[-1]}")
            if details:
                return " · ".join(details)
            return " · ".join(f"{k}: {v}" for k, v in answer.items())
        return str(answer)
    return str(value)

question_label, fact, reference_error = reference_fact(reference["question"])
st.markdown("**Otázka**")
st.write(question_label)
st.markdown("**Co se skutečně stalo**")
if fact:
    st.info(fact)
    st.caption("Referenční skutečnost pochází ze syntetického světa. Pokud nastalo více změn, jsou uvedeny všechny v časovém pořadí.")
else:
    st.error(f"Nelze bezpečně vyhodnotit tento případ: {reference_error}. U tohoto případu lze zvolit „Nelze posoudit“ a pokračovat.")
with st.expander("Technické informace (nepovinné)"):
    st.write(reference["question"])
    st.caption("Referenční svět: " + reference["question"].split(":")[0].split()[-1])

st.markdown("### Posuďte jednotlivé odpovědi")
st.caption("Porovnejte odpověď modelu s uvedenou skutečností. Správně = shoduje se. Špatně = odporuje. Nelze posoudit = odpověď je nejasná.")
for position, record in enumerate(case_rows, start=1):
    rid = record["response_id"]
    selected = ratings.get(rid, {}).get("semantic_correct")
    with st.container(border=True):
        st.markdown(f"**Odpověď {position}:** {answer_summary(record['raw_model_response'])}")
        if selected in ("correct", "incorrect", "ambiguous"):
            st.caption("Zvoleno: " + {"correct": "Správně", "incorrect": "Špatně", "ambiguous": "Nelze posoudit"}[selected])
        cols = st.columns(3)
        for col, key, label in zip(cols, ("correct", "incorrect", "ambiguous"), ("Správně", "Špatně", "Nelze posoudit")):
            if col.button(label, key=f"rate_{rid}_{key}", disabled=(not fact and key != "ambiguous"), use_container_width=True, type="primary" if selected == key else "secondary"):
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
