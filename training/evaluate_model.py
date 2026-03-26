import json
import argparse
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Any

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from rouge_score import rouge_scorer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE  = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_CKPT  = str(PROJECT_ROOT / "model-serving" / "checkpoints")
DEFAULT_VAL   = str(PROJECT_ROOT / "data" / "processed" / "val.jsonl")
DEFAULT_OUT   = str(PROJECT_ROOT / "data" / "rag_eval" / "eval_report.json")
SAMPLE_PRINT  = 10   # 随机打印多少条供人工判断


def load_model(base_model: str, checkpoint: str):
    print(f"[Eval] Loading base model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    print(f"[Eval] Loading LoRA adapter: {checkpoint}")
    model = PeftModel.from_pretrained(model, checkpoint)
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, messages: list, max_new_tokens: int = 256) -> str:
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    # 只取新生成的部分
    new_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_ids, skip_special_tokens=True).strip()


def load_val(val_path: str) -> list:
    samples = []
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def create_visualizations(results: List[Dict[str, Any]], output_dir: Path, checkpoint_name: str):
    """
    创建评估结果的可视化图表
    """
    # 提取ROUGE-L分数
    rouge_scores = [r["rougeL"] for r in results]
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. ROUGE-L分数分布直方图
    plt.figure(figsize=(10, 6))
    plt.hist(rouge_scores, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
    plt.axvline(x=np.mean(rouge_scores), color='red', linestyle='--', 
                label=f'平均值: {np.mean(rouge_scores):.3f}')
    plt.axvline(x=np.median(rouge_scores), color='green', linestyle='--', 
                label=f'中位数: {np.median(rouge_scores):.3f}')
    plt.xlabel('ROUGE-L 分数')
    plt.ylabel('样本数量')
    plt.title(f'ROUGE-L 分数分布 - {checkpoint_name}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    hist_path = output_dir / "rouge_distribution.png"
    plt.tight_layout()
    plt.savefig(hist_path, dpi=150)
    plt.close()
    
    # 2. ROUGE-L分数随时间变化（按样本顺序）
    plt.figure(figsize=(12, 6))
    plt.plot(range(len(rouge_scores)), rouge_scores, 'b-', alpha=0.6, linewidth=1)
    plt.axhline(y=np.mean(rouge_scores), color='red', linestyle='--', 
                label=f'平均值: {np.mean(rouge_scores):.3f}')
    
    # 添加移动平均线
    window_size = min(50, len(rouge_scores) // 10)
    if window_size > 1:
        moving_avg = np.convolve(rouge_scores, np.ones(window_size)/window_size, mode='valid')
        plt.plot(range(window_size-1, len(rouge_scores)), moving_avg, 'g-', 
                linewidth=2, label=f'{window_size}样本移动平均')
    
    plt.xlabel('样本序号')
    plt.ylabel('ROUGE-L 分数')
    plt.title(f'ROUGE-L 分数变化趋势 - {checkpoint_name}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    trend_path = output_dir / "rouge_trend.png"
    plt.tight_layout()
    plt.savefig(trend_path, dpi=150)
    plt.close()
    
    # 3. 分数统计摘要箱线图
    plt.figure(figsize=(8, 6))
    box_data = [rouge_scores]
    box_labels = ['ROUGE-L']
    
    bp = plt.boxplot(box_data, labels=box_labels, patch_artist=True, showmeans=True)
    bp['boxes'][0].set_facecolor('lightblue')
    bp['medians'][0].set_color('red')
    bp['means'][0].set_color('green')
    
    # 添加统计信息文本
    stats_text = f"""
    统计摘要:
    平均值: {np.mean(rouge_scores):.3f}
    中位数: {np.median(rouge_scores):.3f}
    标准差: {np.std(rouge_scores):.3f}
    最小值: {np.min(rouge_scores):.3f}
    最大值: {np.max(rouge_scores):.3f}
    样本数: {len(rouge_scores)}
    """
    plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.ylabel('ROUGE-L 分数')
    plt.title(f'ROUGE-L 分数统计摘要 - {checkpoint_name}')
    plt.grid(True, alpha=0.3)
    box_path = output_dir / "rouge_summary.png"
    plt.tight_layout()
    plt.savefig(box_path, dpi=150)
    plt.close()
    
    # 4. 创建HTML报告
    html_report = create_html_report(results, output_dir, checkpoint_name, rouge_scores)
    
    return {
        "histogram": str(hist_path),
        "trend": str(trend_path),
        "summary": str(box_path),
        "html_report": str(html_report)
    }


def create_html_report(results: List[Dict[str, Any]], output_dir: Path, 
                      checkpoint_name: str, rouge_scores: List[float]) -> Path:
    """
    创建包含可视化图表的HTML报告
    """
    html_path = output_dir / "evaluation_report.html"
    
    # 获取最佳和最差的样本
    sorted_results = sorted(results, key=lambda x: x["rougeL"])
    worst_samples = sorted_results[:5]  # 最差的5个
    best_samples = sorted_results[-5:]  # 最好的5个
    best_samples.reverse()  # 从高到低显示
    
    # 计算统计信息
    stats = {
        "mean": np.mean(rouge_scores),
        "median": np.median(rouge_scores),
        "std": np.std(rouge_scores),
        "min": np.min(rouge_scores),
        "max": np.max(rouge_scores),
        "q1": np.percentile(rouge_scores, 25),
        "q3": np.percentile(rouge_scores, 75),
    }
    
    # 生成HTML内容
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>模型评估报告 - {checkpoint_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 30px; padding: 20px; border: 1px solid #dee2e6; border-radius: 5px; }}
        .section-title {{ color: #495057; border-bottom: 2px solid #6c757d; padding-bottom: 10px; margin-bottom: 15px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .stat-card {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .stat-label {{ font-size: 14px; color: #6c757d; }}
        .image-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .image-container {{ text-align: center; }}
        .image-container img {{ max-width: 100%; height: auto; border: 1px solid #dee2e6; border-radius: 5px; }}
        .sample-table {{ width: 100%; border-collapse: collapse; }}
        .sample-table th, .sample-table td {{ border: 1px solid #dee2e6; padding: 10px; text-align: left; }}
        .sample-table th {{ background-color: #f8f9fa; }}
        .good-score {{ color: #28a745; font-weight: bold; }}
        .bad-score {{ color: #dc3545; font-weight: bold; }}
        .timestamp {{ color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>模型评估报告</h1>
            <p class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <h2>{checkpoint_name}</h2>
            <p>总样本数: {len(results)}</p>
        </div>
        
        <div class="section">
            <h3 class="section-title">统计摘要</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{stats['mean']:.3f}</div>
                    <div class="stat-label">平均ROUGE-L</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['median']:.3f}</div>
                    <div class="stat-label">中位数ROUGE-L</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['std']:.3f}</div>
                    <div class="stat-label">标准差</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['min']:.3f}</div>
                    <div class="stat-label">最低分</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['max']:.3f}</div>
                    <div class="stat-label">最高分</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats['q1']:.3f} - {stats['q3']:.3f}</div>
                    <div class="stat-label">四分位范围</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h3 class="section-title">可视化图表</h3>
            <div class="image-grid">
                <div class="image-container">
                    <img src="rouge_distribution.png" alt="ROUGE-L分数分布">
                    <p>ROUGE-L分数分布直方图</p>
                </div>
                <div class="image-container">
                    <img src="rouge_trend.png" alt="ROUGE-L分数趋势">
                    <p>ROUGE-L分数变化趋势</p>
                </div>
                <div class="image-container">
                    <img src="rouge_summary.png" alt="ROUGE-L统计摘要">
                    <p>ROUGE-L统计摘要箱线图</p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h3 class="section-title">最佳表现样本 (ROUGE-L 最高)</h3>
            <table class="sample-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>问题</th>
                        <th>参考答案</th>
                        <th>模型预测</th>
                        <th>ROUGE-L</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # 添加最佳样本
    for sample in best_samples:
        html_content += f"""
                    <tr>
                        <td>{sample['id']}</td>
                        <td>{sample['question'][:100]}...</td>
                        <td>{sample['ground_truth'][:100]}...</td>
                        <td>{sample['prediction'][:100]}...</td>
                        <td class="good-score">{sample['rougeL']:.4f}</td>
                    </tr>
"""
    
    html_content += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h3 class="section-title">最差表现样本 (ROUGE-L 最低)</h3>
            <table class="sample-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>问题</th>
                        <th>参考答案</th>
                        <th>模型预测</th>
                        <th>ROUGE-L</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # 添加最差样本
    for sample in worst_samples:
        html_content += f"""
                    <tr>
                        <td>{sample['id']}</td>
                        <td>{sample['question'][:100]}...</td>
                        <td>{sample['ground_truth'][:100]}...</td>
                        <td>{sample['prediction'][:100]}...</td>
                        <td class="bad-score">{sample['rougeL']:.4f}</td>
                    </tr>
"""
    
    html_content += f"""
                </tbody>
            </table>
        </div>

        <div class="section">
            <h3 class="section-title">评估详情</h3>
            <p>完整评估结果已保存为JSON文件，包含所有{len(results)}个样本的详细数据。</p>
            <p>可视化图表已保存为PNG格式，可直接用于报告和演示。</p>
        </div>
    </div>
</body>
</html>
"""
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_path


def main():
    parser = argparse.ArgumentParser(description="评估微调后的语言模型并生成可视化报告")
    parser.add_argument("--base_model",  default=DEFAULT_BASE,
                        help="基础模型名称或路径")
    parser.add_argument("--checkpoint",  default=DEFAULT_CKPT,
                        help="LoRA检查点路径")
    parser.add_argument("--val_path",    default=DEFAULT_VAL,
                        help="验证集JSONL文件路径")
    parser.add_argument("--output_path", default=DEFAULT_OUT,
                        help="JSON评估报告输出路径")
    parser.add_argument("--max_samples", type=int, default=-1,
                        help="限制评估条数，-1 表示全量")
    parser.add_argument("--no-visualize", dest="visualize", action="store_false", default=True,
                        help="加此参数则跳过可视化图表生成")
    parser.add_argument("--viz_dir", type=str, default=None,
                        help="可视化文件输出目录，默认为JSON报告同目录")
    cfg = parser.parse_args()

    model, tokenizer = load_model(cfg.base_model, cfg.checkpoint)
    samples = load_val(cfg.val_path)

    if cfg.max_samples > 0:
        samples = samples[:cfg.max_samples]
    print(f"[Eval] Evaluating {len(samples)} samples ...")

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    results = []
    rouge_scores = []

    for i, sample in enumerate(samples):
        messages = sample["messages"]
        # 取 system + user 作为 prompt，assistant 作为 ground truth
        prompt_msgs  = [m for m in messages if m["role"] != "assistant"]
        ground_truth = next(m["content"] for m in messages if m["role"] == "assistant")

        prediction = generate(model, tokenizer, prompt_msgs)
        score = scorer.score(ground_truth, prediction)["rougeL"].fmeasure
        rouge_scores.append(score)

        results.append({
            "id":           i,
            "question":     prompt_msgs[-1]["content"],
            "ground_truth": ground_truth,
            "prediction":   prediction,
            "rougeL":       round(score, 4),
        })

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(samples)}] avg ROUGE-L so far: {sum(rouge_scores)/len(rouge_scores):.4f}")

    avg_rouge = sum(rouge_scores) / len(rouge_scores)
    print(f"\n[Eval] Final avg ROUGE-L: {avg_rouge:.4f}")

    # 人工抽样打印
    print(f"\n{'='*60}")
    print(f"[Eval] Sample outputs (first {SAMPLE_PRINT}):")
    print(f"{'='*60}")
    for r in results[:SAMPLE_PRINT]:
        print(f"\nQ : {r['question']}")
        print(f"GT: {r['ground_truth']}")
        print(f"PR: {r['prediction']}")
        print(f"ROUGE-L: {r['rougeL']}")
        print("-" * 40)

    # 保存报告
    Path(cfg.output_path).parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp":    datetime.now().isoformat(),
        "checkpoint":   cfg.checkpoint,
        "num_samples":  len(samples),
        "avg_rougeL":   round(avg_rouge, 4),
        "results":      results,
    }
    with open(cfg.output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[Eval] JSON报告保存到: {cfg.output_path}")
    
    # 生成可视化图表
    if cfg.visualize:
        print(f"\n[Eval] 生成可视化图表...")
        
        # 确定可视化输出目录
        if cfg.viz_dir:
            viz_dir = Path(cfg.viz_dir)
        else:
            viz_dir = Path(cfg.output_path).parent / "visualizations"
        
        # 提取检查点名称用于标题
        checkpoint_name = Path(cfg.checkpoint).name
        
        try:
            viz_files = create_visualizations(results, viz_dir, checkpoint_name)
            
            print(f"[Eval] 可视化图表生成完成:")
            print(f"  • 分数分布直方图: {viz_files['histogram']}")
            print(f"  • 分数变化趋势图: {viz_files['trend']}")
            print(f"  • 统计摘要箱线图: {viz_files['summary']}")
            print(f"  • HTML评估报告: {viz_files['html_report']}")
            
            # 在报告中添加可视化文件路径
            report["visualization_files"] = viz_files
            with open(cfg.output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[WARN] 可视化生成失败: {e}")
            print("      继续执行，仅保存JSON报告。")
    else:
        print(f"[Eval] 可视化已禁用，使用 --visualize 启用")


if __name__ == "__main__":
    main()
