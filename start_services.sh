#!/bin/bash
# Quant Terminal 启动脚本

echo "=========================================="
echo "Quant Terminal - 启动服务"
echo "=========================================="
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
pip list | grep fastapi > /dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖..."
    pip install -r full_suite_source_bundle_20260421/requirements.txt
fi

# 启动后端服务器
echo ""
echo "启动后端服务器 (端口 8012)..."
cd full_suite_source_bundle_20260421
python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8012 --reload &
BACKEND_PID=$!
echo "后端PID: $BACKEND_PID"

# 等待后端启动
echo "等待后端启动..."
sleep 5

# 启动前端服务器
echo ""
echo "启动前端服务器 (端口 8080)..."
cd ../frontend
python -m http.server 8080 &
FRONTEND_PID=$!
echo "前端PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "服务启动完成！"
echo "=========================================="
echo "后端API: http://localhost:8012"
echo "API文档: http://localhost:8012/docs"
echo "前端应用: http://localhost:8080"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "=========================================="

# 保存PID到文件
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# 等待用户中断
wait
