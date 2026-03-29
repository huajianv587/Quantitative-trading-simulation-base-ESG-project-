import argparse
import inspect
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_TRAIN = str(PROJECT_ROOT / "data" / "processed" / "train.jsonl")
DEFAULT_VAL   = str(PROJECT_ROOT / "data" / "processed" / "val.jsonl")
DEFAULT_OUT   = str(PROJECT_ROOT / "model-serving" / "checkpoints")


def load_model(model_name: str):
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
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


def build_lora(model):
    config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()
    return model


def build_dataset(tokenizer, train_data_path: str, val_data_path: str, max_length: int = 512):
    train_ds = load_dataset("json", data_files=train_data_path, split="train")
    val_ds   = load_dataset("json", data_files=val_data_path,   split="train")

    def _tokenize(x):
        # 数据格式: {"messages": [{"role": ..., "content": ...}, ...]}
        # 用 apply_chat_template 处理 ChatML，只对 assistant 部分计算 loss
        full_text = tokenizer.apply_chat_template(     #apply_chat_template() 会把这种“消息列表格式”，变成模型真正能吃的 聊天文本格式。
            x["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        prompt_msgs = [m for m in x["messages"] if m["role"] != "assistant"]  #把 assistant 的消息去掉，只保留 system/user 等作为 prompt。
        prompt_text = tokenizer.apply_chat_template(     #这里也是把prompt转成文本格式
            prompt_msgs,
            tokenize=False,
            add_generation_prompt=True,
        )

        full   = tokenizer(full_text,   truncation=True, max_length=max_length)  #在这里才进行tokenize
        prompt = tokenizer(prompt_text, truncation=True, max_length=max_length)

        input_ids      = full["input_ids"]
        attention_mask = full["attention_mask"]
        prompt_len     = len(prompt["input_ids"])
        labels         = [-100] * prompt_len + input_ids[prompt_len:]

        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}

    train_ds = train_ds.map(_tokenize, remove_columns=train_ds.column_names)   #map 把 _tokenize 这个函数，应用到数据集里的每一条样本上。
    val_ds   = val_ds.map(_tokenize,   remove_columns=val_ds.column_names)    # remove_columns 把原来旧的字段删掉，只保留 _tokenize 返回的新字段。
    return train_ds, val_ds


def build_trainer(model, tokenizer, ds_train, ds_val, out_dir: str):
    args_kwargs = dict(
        output_dir=out_dir,
        learning_rate=2e-4,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=8,
        num_train_epochs=2,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        fp16=True,
        logging_steps=10,
        save_steps=200,
        eval_steps=200,
        save_total_limit=2,
        load_best_model_at_end=True,
        report_to="none",
    )

    # Different transformers versions use either `eval_strategy`
    # or the older `evaluation_strategy`.
    training_args_params = inspect.signature(TrainingArguments.__init__).parameters
    if "eval_strategy" in training_args_params:
        args_kwargs["eval_strategy"] = "steps"
    else:
        args_kwargs["evaluation_strategy"] = "steps"

    args = TrainingArguments(**args_kwargs)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )
    return trainer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name",      default=DEFAULT_MODEL)
    parser.add_argument("--train_data_path", default=DEFAULT_TRAIN)
    parser.add_argument("--val_data_path",   default=DEFAULT_VAL)
    parser.add_argument("--output_dir",      default=DEFAULT_OUT)
    parser.add_argument("--max_steps",       type=int, default=-1,
                        help="设置 >0 用于快速验证，例如 --max_steps 100")
    cfg = parser.parse_args()

    print(f"[Train] Model : {cfg.model_name}")
    model, tokenizer = load_model(cfg.model_name)
    model = build_lora(model)

    print("[Train] Building dataset ...")
    ds_train, ds_val = build_dataset(tokenizer, cfg.train_data_path, cfg.val_data_path)
    print(f"[Train] train={len(ds_train)}, val={len(ds_val)}")

    trainer = build_trainer(model, tokenizer, ds_train, ds_val, cfg.output_dir)

    if cfg.max_steps > 0:
        trainer.args.max_steps = cfg.max_steps
        print(f"[Train] Quick test mode: max_steps={cfg.max_steps}")

    trainer.train()
    trainer.save_model(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)
    print(f"[Train] Saved to {cfg.output_dir}")


if __name__ == "__main__":
    main()
