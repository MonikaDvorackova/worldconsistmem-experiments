# WorldConsistMem — blind human evaluation

Streamlit app for blinded annotation. Source CSV and private mappings are intentionally **not committed**.

## Local
```bash
cd human_evaluation
export WCM_ACCESS_CODE='choose-a-private-code'
cp ~/Downloads/wcm_validation/BLINDED_ANNOTATION.csv .
pip install -r requirements.txt
streamlit run app.py
```

## Hosting
Deploy the `human_evaluation/app.py` entrypoint on a Streamlit-compatible host. Configure `WCM_ACCESS_CODE` as a secret and provide `BLINDED_ANNOTATION.csv` via a private deployment process. Do **not** commit `PRIVATE_MAPPING.json` or automated scores.

The app saves annotations in browser session memory; the annotator must download progress JSON to resume after session expiry. It does not claim server-side persistence. Export the completed CSV after all rows are rated.

**Research caveat:** Sample inclusion and disagreement coverage must be audited separately before interpreting results. Never publish private keys or dataset without reviewing its disclosure implications.
