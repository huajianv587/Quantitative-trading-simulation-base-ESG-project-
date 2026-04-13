import argparse
import inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _prefer_existing(*paths: Path) -> str:
    for path in paths:
        if path.exists():
            return str(path)
    return str(paths[0])


DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_TRAIN = _prefer_existing(
    PROJECT_ROOT / "data" / "rag_training_data" / "train.jsonl",
    PROJECT_ROOT / "data" / "processed" / "train.jsonl",
)
DEFAULT_VAL = _prefer_existing(
    PROJECT_ROOT / "data" / "rag_training_data" / "val.jsonl",
    PROJECT_ROOT / "data" / "processed" / "val.jsonl",
)
DEFAULT_OUT = _prefer_existing(
    PROJECT_ROOT / "model-serving" / "checkpoint",
    PROJECT_ROOT / "model-serving" / "checkpoints",
)


def load_model(model_name: str, *, precision: str = "auto"):
    import torch
    from peft import prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    compute_dtype = torch.float16
    if precision == "bf16" or (precision == "auto" and torch.cuda.is_available() and torch.cuda.is_bf16_supported()):
        compute_dtype = torch.bfloat16
    elif precision == "fp32":
        compute_dtype = torch.float32

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    return model, tokenizer


def build_lora(model, *, r: int = 16, lora_alpha: int = 32, lora_dropout: float = 0.05):
    from peft import LoraConfig, get_peft_model

    config = LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()
    return model


def build_dataset(tokenizer, train_data_path: str, val_data_path: str, max_length: int = 512):
    from datasets import load_dataset

    train_ds = load_dataset("json", data_files=train_data_path, split="train")
    val_ds = load_dataset("json", data_files=val_data_path, split="train")

    def _tokenize(row):
        full_text = tokenizer.apply_chat_template(
            row["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        prompt_messages = [message for message in row["messages"] if message["role"] != "assistant"]
        prompt_text = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        full = tokenizer(full_text, truncation=True, max_length=max_length)
        prompt = tokenizer(prompt_text, truncation=True, max_length=max_length)

        input_ids = full["input_ids"]
        prompt_len = len(prompt["input_ids"])
        labels = [-100] * prompt_len + input_ids[prompt_len:]

        return {
            "input_ids": input_ids,
            "attention_mask": full["attention_mask"],
            "labels": labels,
        }

    train_ds = train_ds.map(_tokenize, remove_columns=train_ds.column_names)
    val_ds = val_ds.map(_tokenize, remove_columns=val_ds.column_names)
    return train_ds, val_ds


def build_trainer(
    model,
    tokenizer,
    ds_train,
    ds_val,
    out_dir: str,
    *,
    num_train_epochs: int = 2,
    learning_rate: float = 2e-4,
    per_device_train_batch_size: int = 4,
    per_device_eval_batch_size: int = 4,
    gradient_accumulation_steps: int = 8,
    warmup_ratio: float = 0.03,
    lr_scheduler_type: str = "cosine",
    fp16: bool = True,
    bf16: bool = False,
    gradient_checkpointing: bool = False,
    logging_steps: int = 10,
    save_steps: int = 200,
    eval_steps: int = 200,
    save_total_limit: int = 2,
):
    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments

    args_kwargs = dict(
        output_dir=out_dir,
        learning_rate=learning_rate,
        per_device_train_batch_size=per_device_train_batch_size,
        per_device_eval_batch_size=per_device_eval_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        num_train_epochs=num_train_epochs,
        lr_scheduler_type=lr_scheduler_type,
        warmup_ratio=warmup_ratio,
        fp16=fp16,
        bf16=bf16,
        gradient_checkpointing=gradient_checkpointing,
        logging_steps=logging_steps,
        save_steps=save_steps,
        eval_steps=eval_steps,
        save_total_limit=save_total_limit,
        load_best_model_at_end=True,
        report_to="none",
    )

    training_args_params = inspect.signature(TrainingArguments.__init__).parameters
    if "eval_strategy" in training_args_params:
        args_kwargs["eval_strategy"] = "steps"
    else:
        args_kwargs["evaluation_strategy"] = "steps"

    args = TrainingArguments(**args_kwargs)

    trainer_kwargs = dict(
        model=model,
        args=args,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )

    trainer_params = inspect.signature(Trainer.__init__).parameters
    if "processing_class" in trainer_params:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer

    return Trainer(**trainer_kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", default=DEFAULT_MODEL)
    parser.add_argument("--train_data_path", default=DEFAULT_TRAIN)
    parser.add_argument("--val_data_path", default=DEFAULT_VAL)
    parser.add_argument("--output_dir", default=DEFAULT_OUT)
    parser.add_argument("--num_train_epochs", type=int, default=2)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--per_device_train_batch_size", type=int, default=4)
    parser.add_argument("--per_device_eval_batch_size", type=int, default=4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--warmup_ratio", type=float, default=0.03)
    parser.add_argument("--lr_scheduler_type", default="cosine")
    parser.add_argument("--precision", choices=["auto", "fp16", "bf16", "fp32"], default="auto")
    parser.add_argument("--gradient_checkpointing", action="store_true")
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--save_steps", type=int, default=200)
    parser.add_argument("--eval_steps", type=int, default=200)
    parser.add_argument("--save_total_limit", type=int, default=2)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--max_steps",
        type=int,
        default=-1,
        help="Set >0 for a quick verification run, for example --max_steps 100.",
    )
    cfg = parser.parse_args()

    print(f"[Train] Model : {cfg.model_name}")
    model, tokenizer = load_model(cfg.model_name, precision=cfg.precision)
    model = build_lora(
        model,
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
    )

    print("[Train] Building dataset ...")
    ds_train, ds_val = build_dataset(
        tokenizer,
        cfg.train_data_path,
        cfg.val_data_path,
        max_length=cfg.max_length,
    )
    print(f"[Train] train={len(ds_train)}, val={len(ds_val)}")

    fp16 = cfg.precision in {"auto", "fp16"}
    bf16 = cfg.precision == "bf16"
    if cfg.precision == "auto":
        import torch

        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            bf16 = True
            fp16 = False

    trainer = build_trainer(
        model,
        tokenizer,
        ds_train,
        ds_val,
        cfg.output_dir,
        num_train_epochs=cfg.num_train_epochs,
        learning_rate=cfg.learning_rate,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        per_device_eval_batch_size=cfg.per_device_eval_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        warmup_ratio=cfg.warmup_ratio,
        lr_scheduler_type=cfg.lr_scheduler_type,
        fp16=fp16,
        bf16=bf16,
        gradient_checkpointing=cfg.gradient_checkpointing,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        eval_steps=cfg.eval_steps,
        save_total_limit=cfg.save_total_limit,
    )

    if cfg.max_steps > 0:
        trainer.args.max_steps = cfg.max_steps
        print(f"[Train] Quick test mode: max_steps={cfg.max_steps}")

    trainer.train()
    trainer.save_model(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)
    print(f"[Train] Saved to {cfg.output_dir}")


if __name__ == "__main__":
    main()
