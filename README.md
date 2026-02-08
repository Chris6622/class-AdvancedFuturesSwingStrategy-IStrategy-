# 🚀 Freqtrade Advanced Futures Swing Strategy

Professional-grade cryptocurrency futures swing trading bot with multi-timeframe analysis, automated hyperopt, and cloud deployment.

[![Deploy to Linode](https://img.shields.io/badge/Deploy-Linode-00A95C?logo=linode)](./LINODE_DEPLOYMENT.md)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](./Dockerfile)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?logo=kubernetes)](./kubernetes/)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform)](./terraform/)

## ✨ Features

### 📊 Advanced Trading Strategy
- **Multi-Timeframe Analysis** (15m, 1h, 4h, 1d)
- **Smart Money Concepts** (Accumulation/Distribution zones)
- **Support & Resistance Detection** with order flow confirmation
- **Long Wick Analysis** (rejection patterns)
- **Order Flow Approximation** (volume delta tracking)
- **Dynamic Risk Management** (ATR-based stops)

### 🤖 Automation
- **Quarterly Hyperopt** - Automatically optimizes strategy every 3 months
- **Auto Parameter Injection** - Updates strategy with best parameters
- **Telegram Notifications** - Real-time alerts and reports
- **Cron-based Scheduling** - Set and forget

### 🏗️ Production Ready
- **Docker & Kubernetes** deployment
- **Infrastructure as Code** (Terraform for AWS, GCP, Azure, Linode)
- **CI/CD Pipeline** (GitHub Actions)
- **Monitoring** (Prometheus, Grafana, Loki)
- **Automated Backups**

## 💰 Cost Comparison

| Provider | Monthly Cost | Link |
|----------|--------------|------|
| **Linode** ⭐ | **~$180-240** | [Deploy Guide](./LINODE_DEPLOYMENT.md) |
| AWS | ~$300-500 | [Deploy Guide](./DEPLOYMENT.md) |
| GCP | ~$250-450 | [Deploy Guide](./DEPLOYMENT.md) |
| Azure | ~$300-500 | [Deploy Guide](./DEPLOYMENT.md) |

## 🎯 Quick Start

### Prerequisites
- Docker
- Python 3.11+
- Exchange API keys (Binance, etc.)
- Telegram bot (optional)

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd ft_userdata
```

### 2. Configure Environment
```bash
cp .env.example .env
nano .env  # Edit with your API keys
```

### 3. Run Locally (Docker)
```bash
# Build
docker-compose build

# Start (dry run mode)
docker-compose up -d

# View logs
docker-compose logs -f freqtrade
```

### 4. Deploy to Cloud
Choose your provider:
- **Linode** (Recommended): [LINODE_DEPLOYMENT.md](./LINODE_DEPLOYMENT.md)
- **AWS/GCP/Azure**: [DEPLOYMENT.md](./DEPLOYMENT.md)

## 📁 Project Structure

```
ft_userdata/
├── user_data/
│   └── strategies/
│       └── AdvancedFuturesSwingStrategy.py  # Main strategy
├── scripts/
│   ├── deploy.sh                # Multi-cloud deployment
│   ├── deploy-linode.sh         # Linode-specific
│   ├── run_hyperopt.sh          # Hyperopt automation
│   ├── inject_hyperopt_params.py
│   ├── compare_results.py
│   └── send_notification.py     # Telegram alerts
├── kubernetes/
│   └── deployment.yaml          # K8s manifests
├── terraform/
│   ├── aws/                     # AWS infrastructure
│   ├── linode/                  # Linode infrastructure
│   ├── gcp/                     # GCP infrastructure (add if needed)
│   └── azure/                   # Azure infrastructure (add if needed)
├── monitoring/
│   ├── prometheus.yml
│   ├── grafana/
│   └── loki-config.yml
├── docker-compose.yml           # Local development
├── Dockerfile                   # Container image
├── .env.example                 # Environment template
└── README.md                    # This file
```

## 🎛️ Strategy Configuration

The strategy includes extensive hyperopt parameters that are automatically optimized quarterly:

- **Trend Analysis**: HTF EMA periods, accumulation zones
- **Volume**: Surge detection, confirmation levels
- **Wicks**: Upper/lower wick thresholds
- **Support/Resistance**: Dynamic level detection
- **RSI/ADX**: Momentum and trend strength
- **Order Flow**: Delta thresholds

## 📈 Strategy Logic

### Entry Conditions (LONG)

1. **HTF Bullish Trend + Accumulation Breakout**
   - All higher timeframes bullish
   - Previous accumulation detected
   - Positive order flow
   - Volume confirmation

2. **Wyckoff Spring Pattern**
   - False breakdown detected
   - Order flow reversal
   - Volume surge

3. **Support Bounce**
   - Price at dynamic support
   - Long lower wick (rejection)
   - Positive cumulative delta

4. **Pullback Entry**
   - Strong HTF trend
   - Pullback to moving average
   - Order flow confirmation

### Exit Conditions

- Distribution zone detection
- Resistance rejection
- HTF trend reversal
- Upthrust (false breakout)
- Momentum loss

## 🔄 Automated Hyperopt

Runs quarterly (Jan 1, Apr 1, Jul 1, Oct 1) at 2 AM UTC:

1. Downloads fresh market data
2. Optimizes 500 epochs
3. Backtests new parameters
4. Compares with previous results
5. Auto-injects if improved
6. Sends Telegram notification with results

## 📱 Telegram Setup

1. Create bot with [@BotFather](https://t.me/BotFather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```
4. Test: `python scripts/test_telegram.py`

See [TELEGRAM_SETUP.md](./TELEGRAM_SETUP.md) for details.

## 🐳 Docker Compose Services

- **freqtrade** - Main trading bot
- **postgres** - Trade database
- **redis** - Caching layer
- **grafana** - Monitoring dashboards
- **prometheus** - Metrics collection
- **loki** - Log aggregation
- **nginx** - Reverse proxy

## ☁️ Cloud Deployment

### Linode (Recommended)
```bash
cd terraform/linode
terraform init
terraform apply
```
See [LINODE_DEPLOYMENT.md](./LINODE_DEPLOYMENT.md)

### AWS
```bash
cd terraform/aws
terraform init
terraform apply
```
See [DEPLOYMENT.md](./DEPLOYMENT.md)

## 📊 Monitoring

Access dashboards after deployment:
- **Grafana**: http://your-ip:3000 (admin/admin)
- **Prometheus**: http://your-ip:9090
- **FreqUI**: http://your-ip:8082

## 🔒 Security

- API keys stored in Kubernetes secrets
- Database encrypted at rest
- TLS/SSL for external access
- Network policies
- Regular security updates

## 📝 Configuration Files

### Required Configuration
1. **`.env`** - API keys, passwords
2. **`user_data/config.json`** - Freqtrade settings
3. **`terraform/*.tfvars`** - Infrastructure variables

### Optional Configuration
- **`monitoring/grafana/dashboards/`** - Custom dashboards
- **`kubernetes/network-policies.yaml`** - Network rules

## 🧪 Testing

```bash
# Validate strategy
freqtrade test-strategy --strategy AdvancedFuturesSwingStrategy

# Backtest
freqtrade backtesting \
  --strategy AdvancedFuturesSwingStrategy \
  --timerange 20240101-20240201

# Plot results
freqtrade plot-dataframe \
  --strategy AdvancedFuturesSwingStrategy
```

## 🔧 Troubleshooting

### Common Issues

**Pods not starting**
```bash
kubectl describe pod <pod-name> -n freqtrade
kubectl logs <pod-name> -n freqtrade
```

**Database connection failed**
```bash
kubectl exec -it deployment/postgres -n freqtrade -- psql -U freqtrade
```

**API not accessible**
```bash
kubectl get svc -n freqtrade
kubectl describe ingress -n freqtrade
```

See full troubleshooting in [LINODE_DEPLOYMENT.md](./LINODE_DEPLOYMENT.md#-troubleshooting)

## 📚 Documentation

- [Linode Deployment Guide](./LINODE_DEPLOYMENT.md)
- [AWS/GCP/Azure Guide](./DEPLOYMENT.md)
- [Telegram Setup](./TELEGRAM_SETUP.md)
- [Freqtrade Docs](https://www.freqtrade.io/en/stable/)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

## ⚠️ Disclaimer

**Trading cryptocurrencies involves substantial risk of loss.**

- This software is provided "as-is" without warranty
- Past performance does not guarantee future results
- Start with paper trading (DRY_RUN=true)
- Never trade with money you can't afford to lose
- Do your own research before trading

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- [Freqtrade](https://github.com/freqtrade/freqtrade) - Trading bot framework
- Community contributors and testers

## 📞 Support

- 💬 Issues: [GitHub Issues](../../issues)
- 📖 Docs: See documentation files in this repo
- 🐛 Bugs: [Report here](../../issues/new)

---

## 🚀 Quick Deploy Commands

**Linode:**
```bash
./scripts/deploy-linode.sh
```

**AWS:**
```bash
./scripts/deploy.sh aws production deploy
```

**Local Docker:**
```bash
docker-compose up -d
```

---

**Built with ❤️ for profitable crypto trading**

**Last Updated:** February 2026  
**Version:** 1.0.0
