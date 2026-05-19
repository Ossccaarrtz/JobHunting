# Job Search Agent

Automated agent that searches for software engineering internships, filters them with AI against a personal profile, and sends matching jobs to Telegram. Runs entirely on AWS at $0/month.

## How it works

```
EventBridge (every 8h)
  → Lambda (Python 3.12)
    → JSearch API      — fetch fresh job listings
    → Groq (LLaMA 3.1) — AI relevance filtering
    → DynamoDB         — skip already-seen jobs
    → Telegram Bot     — notify only new matches
```

Each run:
1. Fetches jobs from JSearch (last 3 days, deduped by DynamoDB)
2. Filters them with LLaMA 3.1 against your `profile.json`
3. Sends matching jobs to Telegram with apply links
4. If no matches: notifies "no matches this run"
5. If no new jobs at all: sends one daily heartbeat so you know the agent is alive

## Stack

| Component | Service | Cost |
|---|---|---|
| Scheduler | AWS EventBridge | Free |
| Runtime | AWS Lambda (Python 3.12) | Free (1M req/month) |
| Job search | JSearch API (RapidAPI) | Free (200 req/month) |
| AI filtering | Groq — LLaMA 3.1 8B | Free |
| Deduplication | AWS DynamoDB | Free (25GB) |
| Notifications | Telegram Bot API | Free forever |

**Estimated total cost: $0/month**

## Project structure

```
job-search-agent/
├── handler.py        # Lambda entry point — orchestrates the full flow
├── searcher.py       # JSearch API integration
├── filter.py         # Groq AI filtering
├── storage.py        # DynamoDB operations (dedup + heartbeat)
├── notifier.py       # Telegram notifications
├── profile.json      # Your profile — source of truth for AI filtering
├── package.py        # Packaging script (cross-platform, used by deploy.sh)
├── deploy.sh         # Full deploy script (packaging + Lambda + EventBridge)
├── requirements.txt
└── .env.example
```

## Setup

### 1. Prerequisites

- Python 3.12+
- AWS CLI configured (`aws configure`)
- Git Bash (Windows) or any bash shell

### 2. Clone and configure

```bash
git clone <repo-url>
cd job-search-agent
cp .env.example .env
```

Fill in `.env`:

```env
JSEARCH_API_KEY=       # RapidAPI → JSearch → Subscribe (free tier)
GROQ_API_KEY=          # console.groq.com → API Keys
TELEGRAM_BOT_TOKEN=    # @BotFather on Telegram → /newbot
TELEGRAM_CHAT_ID=      # Your personal chat ID (see below)
DYNAMODB_TABLE=job-search-seen
AWS_REGION=us-east-1
```

**Getting your Telegram chat ID:**
1. Start a conversation with your bot
2. Open: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Copy the `id` field from the `chat` object

### 3. Create AWS infrastructure

Run these once before deploying:

```bash
# DynamoDB table
aws dynamodb create-table \
  --table-name job-search-seen \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Enable TTL (auto-cleanup after 30 days)
aws dynamodb update-time-to-live \
  --table-name job-search-seen \
  --time-to-live-specification "Enabled=true,AttributeName=expires_at"

# IAM role for Lambda
aws iam create-role \
  --role-name job-search-lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name job-search-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
  --role-name job-search-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
```

### 4. Deploy

```bash
bash deploy.sh
```

This will:
- Install Linux-compatible dependencies
- Package everything into a zip
- Create (or update) the Lambda function
- Set all environment variables on Lambda
- Create the EventBridge rule (`rate(8 hours)`)

### 5. Test

```bash
# Invoke manually
aws lambda invoke \
  --function-name job-search-agent \
  --region us-east-1 \
  response.json && type response.json  # Windows
  # or: cat response.json              # Mac/Linux

# Check logs
aws logs tail /aws/lambda/job-search-agent --region us-east-1
```

Expected output: `{"procesados": N, "notificados": M}`

### Redeploy after code changes

```bash
bash deploy.sh
```

## Customization

Edit `profile.json` to match your own profile. The key sections for AI filtering are:

```json
{
  "rol_buscado": { "titulos": [...] },
  "skills": { ... },
  "criterios_match_ia": {
    "must_have": [...],
    "nice_to_have": [...],
    "dealbreakers": [...]
  }
}
```

To add more search queries, edit `QUERIES` in `searcher.py`. Keep in mind the JSearch free tier limit of 200 requests/month (2 queries × 3 runs/day × 30 days = 180 req/month).
