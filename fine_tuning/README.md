# Module 9 — Fine-Tuning Experiment

QLoRA fine-tuning of Mistral-7B to improve citation formatting consistency.

## The Experiment

| Dimension | Detail |
|-----------|--------|
| **Hypothesis** | A fine-tuned Mistral-7B produces more consistent structured citation output than GPT-4o-mini with prompt engineering |
| **Baseline** | GPT-4o-mini + citation formatting prompt. Metric: schema compliance rate |
| **Intervention** | QLoRA fine-tune on 800 synthetic examples |
| **Primary metric** | Schema compliance rate (% outputs matching target JSON schema exactly) |
| **Decision rule** | Fine-tune wins if compliance > baseline AND inference cost is lower |

## Structure

```
fine_tuning/
├── README.md                   # This file
├── generate_training_data.py   # Generate synthetic examples with GPT-4o
├── train.ipynb                 # Colab/Kaggle training notebook
├── evaluate.py                 # Compare baseline vs fine-tuned model
├── data/
│   ├── train.jsonl             # 720 training examples (generated)
│   └── eval.jsonl              # 80 eval examples (generated)
└── results/
    └── .gitkeep
```

## Running

### Step 1 — Generate training data (local)
```bash
python fine_tuning/generate_training_data.py --n 800 --output fine_tuning/data/
```

### Step 2 — Train (Colab or Kaggle — free T4 GPU)
Upload `train.ipynb` to Google Colab or Kaggle, run all cells.
Training takes ~2-3 hours on a free T4 GPU.

### Step 3 — Evaluate
```bash
python fine_tuning/evaluate.py --adapter ./results/citation-mistral-lora
```

### Step 4 — Deploy locally (optional)
```bash
# Convert to GGUF for Ollama
python fine_tuning/convert_to_gguf.py --adapter ./results/citation-mistral-lora
ollama create citation-mistral -f ./Modelfile
```

## TODO
- [ ] Run `generate_training_data.py` — needs OPENAI_API_KEY
- [ ] Upload `train.ipynb` to Colab and run training
- [ ] Run `evaluate.py` to get baseline vs fine-tuned comparison
- [ ] Update `.env`: `USE_FINETUNED_CITATIONS=true` and `FINETUNED_MODEL_PATH=...`
