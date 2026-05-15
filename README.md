# MennaNUYe Automation Toolkit

This repository now includes a production-oriented Python automation ecosystem for a WooCommerce/MySQL catalog website.

## What is included

- **Module 1:** automated supplier CSV/static-page product synchronization with price guardrails.
- **Module 2:** automated marketing copy, promotional image generation, Telegram posting, and Meta/Facebook posting.
- **Module 3:** database-grounded customer-service chatbot engine with English/Amharic-aware FAQ handling and human handoff.
- **Module 4:** backup automation, SEO broken-link scanning/sitemap generation, uptime monitoring, and database integrity alerts.

Read the complete architecture, setup, cron examples, and operational guidance in [`docs/automation_architecture.md`](docs/automation_architecture.md).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p data media backups
cp data_sample_supplier_products.csv data/supplier_products.csv
```

Edit `.env` with real credentials, then run a safe validation:

```bash
python -m automation.modules.product_sync --dry-run
```

All modules use centralized logging to `automation.log`.
