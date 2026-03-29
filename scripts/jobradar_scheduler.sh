#!/bin/bash
# JobRadar 定时任务管理脚本
# 用途：管理JobRadar的定时爬取任务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
JOB_RADAR_ROOT="$PROJECT_ROOT/JobRadar"
BACKEND_ROOT="$JOB_RADAR_ROOT/backend"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查后端服务状态
check_backend() {
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 查看定时任务状态
status() {
    echo_info "检查JobRadar定时任务状态..."
    
    if check_backend; then
        # 使用API查看定时任务状态
        response=$(curl -s http://localhost:8000/api/scheduler 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            echo "$response"
        else
            echo_error "无法获取定时任务状态"
            return 1
        fi
    else
        echo_error "JobRadar后端服务未运行"
        return 1
    fi
}

# 手动触发定时爬取
trigger() {
    echo_info "手动触发定时爬取任务..."
    
    if check_backend; then
        response=$(curl -s -X POST http://localhost:8000/api/crawl/trigger 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            echo_info "爬取任务已触发"
            echo "$response"
        else
            echo_error "触发爬取任务失败"
            return 1
        fi
    else
        echo_error "JobRadar后端服务未运行"
        return 1
    fi
}

# 启动定时任务
start() {
    echo_info "启动JobRadar定时任务..."
    
    # 检查后端服务是否运行
    if ! check_backend; then
        echo_error "JobRadar后端服务未运行，请先启动后端服务"
        echo_info "启动后端服务: cd $BACKEND_ROOT && source .venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
        return 1
    fi
    
    # 定时任务会随着后端启动自动启动
    echo_info "定时任务已随后端服务启动"
    echo_info "当前配置: 每天早上8点自动爬取"
    
    status
}

# 停止定时任务
stop() {
    echo_warn "停止JobRadar定时任务..."
    echo_warn "注意：定时任务集成在后端服务中，停止后端服务即可停止定时任务"
    echo_info "停止后端服务: kill \$(ps aux | grep 'uvicorn app.main:app' | grep -v grep | awk '{print \$2}')"
}

# 更新定时任务时间
update_cron() {
    local cron_expr="$1"
    
    if [ -z "$cron_expr" ]; then
        echo_error "请提供cron表达式"
        echo "用法: $0 update_cron \"分 时 日 月 周\""
        echo "示例: $0 update_cron \"0 9 * * *\"  (每天早上9点)"
        return 1
    fi
    
    echo_info "更新定时任务时间为: $cron_expr"
    
    # 通过API更新cron表达式
    response=$(curl -s -X PUT http://localhost:8000/api/scheduler -H "Content-Type: application/json" -d "{\"cron\": \"$cron_expr\"}" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo_info "定时任务时间已更新"
        echo "$response"
    else
        echo_error "更新定时任务时间失败"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
JobRadar 定时任务管理脚本

用法: $0 [命令] [参数]

命令:
    status       查看定时任务状态
    trigger      手动触发定时爬取
    start        启动定时任务（需先启动后端服务）
    stop         停止定时任务（停止后端服务）
    update_cron  更新定时任务时间
    help         显示帮助信息

示例:
    $0 status           # 查看定时任务状态
    $0 trigger          # 手动触发爬取
    $0 update_cron "0 9 * * *"   # 改为每天早上9点爬取

当前配置:
    - 运行时间: 每天早上8点
    - 时区: Asia/Shanghai (中国标准时间)
    - 时区对应时间: 北京时间/上海时间

注意:
    - 定时任务集成在后端服务中，随后端启动而启动
    - 定时任务会执行全量爬取和评分
    - 爬取日志可通过后端API查看

作者: JobRadar Team
EOF
}

# 主函数
main() {
    case "$1" in
        status)
            status
            ;;
        trigger)
            trigger
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        update_cron)
            update_cron "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 如果没有参数，显示帮助
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

main "$@"
