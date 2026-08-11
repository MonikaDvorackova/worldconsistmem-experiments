# Model download validation (H4)

- mlx: `0.32.0`
- mlx_lm: `0.31.3`
- disk free: 29.16 GB
- decoding: `{"temperature": 0.0, "max_tokens": 48, "early_stop_on_json": true, "path": "mlx_lm.stream_generate"}`
- evidence_json_cap_chars: 1200; max_tokens: 48; max_evidence_items: 3
- note: load+smoke verified at worker start one model at a time (M1 8GB)

## mlx-community/Qwen2.5-3B-Instruct-4bit

- complete_weights: True
- weight_bytes: 1736293090
- cache_dir: `/Users/monikadvorackova/.cache/huggingface/hub/models--mlx-community--Qwen2.5-3B-Instruct-4bit`
  - .gitattributes: 1519 bytes
  - README.md: 755 bytes
  - added_tokens.json: 605 bytes
  - config.json: 785 bytes
  - merges.txt: 1671853 bytes
  - model.safetensors: 1736293090 bytes
  - model.safetensors.index.json: 66290 bytes
  - special_tokens_map.json: 613 bytes
  - tokenizer.json: 7031673 bytes
  - tokenizer_config.json: 7308 bytes
  - vocab.json: 2776833 bytes

## mlx-community/Phi-3.5-mini-instruct-4bit

- complete_weights: True
- weight_bytes: 2149696133
- cache_dir: `/Users/monikadvorackova/.cache/huggingface/hub/models--mlx-community--Phi-3.5-mini-instruct-4bit`
  - .gitattributes: 1519 bytes
  - README.md: 890 bytes
  - added_tokens.json: 293 bytes
  - config.json: 4149 bytes
  - configuration_phi3.py: 11153 bytes
  - model.safetensors: 2149696133 bytes
  - model.safetensors.index.json: 32695 bytes
  - modeling_phi3.py: 73814 bytes
  - sample_finetune.py: 6131 bytes
  - special_tokens_map.json: 569 bytes
  - tokenizer.json: 1844436 bytes
  - tokenizer.model: 499723 bytes
  - tokenizer_config.json: 3352 bytes

