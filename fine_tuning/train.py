# ─────────────────────────────────────────────────────────────────────────────
#  Module 9 — QLoRA Fine-Tuning Notebook
#  Run on Google Colab (free T4 GPU) or Kaggle
#
#  How to use:
#  1. Upload this file to Colab: File → Upload notebook
#     OR save as train.ipynb using: jupytext --to notebook train.py
#  2. Set runtime to GPU: Runtime → Change runtime type → T4 GPU
#  3. Upload your fine_tuning/data/train.jsonl and eval.jsonl
#  4. Run all cells — training takes ~2-3 hours on T4
# ─────────────────────────────────────────────────────────────────────────────

# %% [markdown]
# ## Cell 1 — Install dependencies

# %%
# !pip install -q transformers peft trl bitsandbytes accelerate datasets wandb

# %% [markdown]
# ## Cell 2 — Imports and config

# %%
import json
import os
from pathlib import Path

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

# ── Config — adjust these if needed ──────────────────────────────────────────
MODEL_ID      = "mistralai/Mistral-7B-Instruct-v0.3"
OUTPUT_DIR    = "./citation-mistral-lora"
WANDB_PROJECT = "enterprise-rag-finetune"    # set to "" to disable W&B
MAX_SEQ_LEN   = 1024

# LoRA hyperparameters
LORA_R        = 16     # rank — higher = more expressive, more memory
LORA_ALPHA    = 32
LORA_DROPOUT  = 0.05

# Training hyperparameters
NUM_EPOCHS    = 3
BATCH_SIZE    = 4
GRAD_ACCUM    = 4      # effective batch = BATCH_SIZE * GRAD_ACCUM = 16
LR            = 2e-4

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

# %% [markdown]
# ## Cell 3 — Load dataset

# %%
def load_jsonl(path: str) -> Dataset:
    """Load a .jsonl file into a HuggingFace Dataset."""
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line.strip()))
    return Dataset.from_list(records)


# TODO: upload your train.jsonl and eval.jsonl to Colab, then:
train_dataset = load_jsonl("train.jsonl")
eval_dataset  = load_jsonl("eval.jsonl")

print(f"Train: {len(train_dataset)} examples")
print(f"Eval:  {len(eval_dataset)} examples")
print(f"\nSample:\n{train_dataset[0]}")

# %% [markdown]
# ## Cell 4 — Format training examples

# %%
def format_example(example: dict) -> dict:
    """
    Format a training example into the Mistral instruction format.
    Mistral uses [INST] ... [/INST] markers.
    """
    instruction = example["instruction"]
    user_input  = example["input"]
    output      = json.dumps(example["output"], indent=2)

    text = (
        f"<s>[INST] {instruction}\n\n{user_input} [/INST]\n"
        f"{output}</s>"
    )
    return {"text": text}


train_dataset = train_dataset.map(format_example)
eval_dataset  = eval_dataset.map(format_example)

print("Formatted example:")
print(train_dataset[0]["text"][:500] + "...")

# %% [markdown]
# ## Cell 5 — Load model with 4-bit quantisation (QLoRA)

# %%
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
model.config.use_cache = False

print(f"Model loaded — parameters: {model.num_parameters():,}")

# %% [markdown]
# ## Cell 6 — Apply LoRA adapters

# %%
lora_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=LORA_DROPOUT,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# Expected output:
# trainable params: ~42M || all params: ~7.2B || trainable%: ~0.58%

# %% [markdown]
# ## Cell 7 — Train

# %%
if WANDB_PROJECT:
    import wandb
    wandb.login()   # will prompt for API key
    os.environ["WANDB_PROJECT"] = WANDB_PROJECT

training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    fp16=True,
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=50,
    save_strategy="steps",
    save_steps=100,
    load_best_model_at_end=True,
    report_to="wandb" if WANDB_PROJECT else "none",
    max_seq_length=MAX_SEQ_LEN,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    args=training_args,
    tokenizer=tokenizer,
)

print("Starting training...")
trainer.train()

# %% [markdown]
# ## Cell 8 — Save adapter

# %%
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"LoRA adapter saved to {OUTPUT_DIR}")
print("Download this folder and point FINETUNED_MODEL_PATH in .env to it")

# %% [markdown]
# ## Cell 9 — Quick evaluation (schema compliance)

# %%
def check_schema_compliance(output_str: str) -> bool:
    """Check if model output matches the required citation JSON schema."""
    try:
        data = json.loads(output_str)
        assert "answer" in data and isinstance(data["answer"], str)
        assert "citations" in data and isinstance(data["citations"], list)
        assert "confidence" in data and 0 <= data["confidence"] <= 1
        for cit in data["citations"]:
            assert "paper_id" in cit
            assert "claim" in cit
            assert "quote_fragment" in cit
        return True
    except (json.JSONDecodeError, AssertionError, KeyError):
        return False


# TODO: run inference on eval_dataset and compute compliance rate
# Compare against your GPT-4o-mini baseline to validate the experiment hypothesis
