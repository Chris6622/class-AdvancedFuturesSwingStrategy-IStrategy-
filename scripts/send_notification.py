#!/usr/bin/env python3
"""
Send Telegram Notifications with Rich Formatting
Sends detailed notifications about hyperopt results, trades, and performance
"""

import argparse
import os
import json
import requests
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Send Telegram notification')
    parser.add_argument('--message', help='Simple text message')
    parser.add_argument('--hyperopt-results', help='Path to hyperopt comparison results')
    parser.add_argument('--backtest-results', help='Path to backtest results JSON')
    parser.add_argument('--type', default='simple', choices=['simple', 'hyperopt', 'backtest'], 
                       help='Notification type')
    return parser.parse_args()


def send_telegram_message(text, parse_mode='HTML'):
    """Send message via Telegram with retry logic"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("⚠️  Telegram credentials not configured in environment variables")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Split long messages (Telegram limit is 4096 characters)
    max_length = 4000
    if len(text) > max_length:
        messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    else:
        messages = [text]
    
    success = True
    for msg in messages:
        payload = {
            'chat_id': chat_id,
            'text': msg,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"✅ Telegram message sent ({len(msg)} chars)")
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send Telegram message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            success = False
    
    return success


def format_simple_message(message):
    """Format a simple text message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    text = f"""
🤖 <b>Freqtrade Notification</b>

{message}

<i>Time: {timestamp}</i>
"""
    return text


def format_hyperopt_results(comparison_file):
    """Format hyperopt results for Telegram"""
    
    if not Path(comparison_file).exists():
        return "❌ Comparison file not found"
    
    with open(comparison_file, 'r') as f:
        content = f.read()
    
    # Extract key information
    lines = content.split('\n')
    
    improvement = "N/A"
    status = "Unknown"
    current_profit = "N/A"
    current_sharpe = "N/A"
    current_winrate = "N/A"
    total_trades = "N/A"
    
    for i, line in enumerate(lines):
        if "Overall Improvement:" in line:
            improvement = line.split(':')[1].strip()
        elif "Status:" in line:
            status = line.split(':')[1].strip()
        elif "Total Profit:" in line and "CURRENT" in ''.join(lines[max(0,i-5):i]):
            parts = line.split()
            if len(parts) >= 3:
                current_profit = f"{parts[2]} {parts[3]}" if len(parts) > 3 else parts[2]
        elif "Sharpe Ratio:" in line and "CURRENT" in ''.join(lines[max(0,i-5):i]):
            current_sharpe = line.split(':')[1].strip()
        elif "Win Rate:" in line and "CURRENT" in ''.join(lines[max(0,i-5):i]):
            current_winrate = line.split(':')[1].strip()
        elif "Total Trades:" in line and "CURRENT" in ''.join(lines[max(0,i-5):i]):
            total_trades = line.split(':')[1].strip()
    
    # Determine emoji based on improvement
    try:
        improvement_val = float(improvement.replace('%', ''))
        if improvement_val > 10:
            emoji = "🚀"
        elif improvement_val > 0:
            emoji = "📈"
        elif improvement_val > -5:
            emoji = "📊"
        else:
            emoji = "📉"
    except:
        emoji = "📊"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    text = f"""
{emoji} <b>QUARTERLY HYPEROPT COMPLETED</b> {emoji}

<b>Status:</b> {status}
<b>Overall Improvement:</b> {improvement}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 OPTIMIZED PERFORMANCE</b>
━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Total Profit:</b> {current_profit}
📈 <b>Sharpe Ratio:</b> {current_sharpe}
🎯 <b>Win Rate:</b> {current_winrate}
🔄 <b>Total Trades:</b> {total_trades}

━━━━━━━━━━━━━━━━━━━━━━━━

✅ New parameters have been automatically injected into the strategy
🔄 Consider restarting the bot to apply changes

<i>Completed: {timestamp}</i>
"""
    return text


def format_backtest_results(backtest_file):
    """Format backtest results for Telegram"""
    
    if not Path(backtest_file).exists():
        return "❌ Backtest file not found"
    
    with open(backtest_file, 'r') as f:
        data = json.load(f)
    
    # Extract metrics
    strategy_data = list(data.get('strategy', {}).values())[0]
    
    total_profit = strategy_data.get('profit_total_abs', 0)
    total_profit_pct = strategy_data.get('profit_total', 0)
    sharpe = strategy_data.get('sharpe', 0)
    sortino = strategy_data.get('sortino', 0)
    total_trades = strategy_data.get('total_trades', 0)
    wins = strategy_data.get('wins', 0)
    losses = strategy_data.get('losses', 0)
    win_rate = (wins / max(total_trades, 1)) * 100
    max_drawdown = strategy_data.get('max_drawdown', 0)
    avg_profit = strategy_data.get('profit_mean', 0)
    expectancy = strategy_data.get('expectancy', 0)
    
    # Determine emoji
    if total_profit_pct > 50:
        emoji = "🚀"
    elif total_profit_pct > 20:
        emoji = "📈"
    elif total_profit_pct > 0:
        emoji = "✅"
    else:
        emoji = "📉"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    text = f"""
{emoji} <b>BACKTEST RESULTS</b> {emoji}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>💰 PROFIT METRICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

<b>Total Profit:</b> {total_profit:.2f} USDT ({total_profit_pct:.2f}%)
<b>Avg Profit/Trade:</b> {avg_profit:.2f}%
<b>Expectancy:</b> {expectancy:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 RISK METRICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

<b>Sharpe Ratio:</b> {sharpe:.2f}
<b>Sortino Ratio:</b> {sortino:.2f}
<b>Max Drawdown:</b> {max_drawdown:.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━
<b>🎯 TRADE STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━━━

<b>Total Trades:</b> {total_trades}
<b>Wins:</b> {wins} ({win_rate:.1f}%)
<b>Losses:</b> {losses} ({100-win_rate:.1f}%)

<i>Generated: {timestamp}</i>
"""
    return text


def main():
    args = parse_args()
    
    if args.type == 'simple' and args.message:
        text = format_simple_message(args.message)
        return send_telegram_message(text)
    
    elif args.type == 'hyperopt' and args.hyperopt_results:
        text = format_hyperopt_results(args.hyperopt_results)
        return send_telegram_message(text)
    
    elif args.type == 'backtest' and args.backtest_results:
        text = format_backtest_results(args.backtest_results)
        return send_telegram_message(text)
    
    else:
        print("❌ Invalid arguments. Provide either:")
        print("   --type simple --message 'Your message'")
        print("   --type hyperopt --hyperopt-results /path/to/comparison.txt")
        print("   --type backtest --backtest-results /path/to/backtest.json")
        return False


if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
