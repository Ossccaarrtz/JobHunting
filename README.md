# 🤖 Job Search Agent

> Automated internship hunter — searches, filters with AI, and pings you on Telegram. Runs 24/7 on AWS at **$0/month**.

```
EventBridge (every 8h) → Lambda → JSearch API → Groq LLaMA 3.1 → DynamoDB → Telegram
```

---

## What it does

Every 8 hours, without you lifting a finger:

1. **Fetches** fresh software engineering internships from JSearch (aggregates LinkedIn, Indeed, Glassdoor)
2. **Filters** them with LLaMA 3.1 against your `profile.json` — skills, dealbreakers, citizenship, everything
3. **Skips** jobs you've already seen (DynamoDB deduplication)
4. **Sends** only the relevant ones to your Telegram with direct apply links
5. **Heartbeat** — if the agent ran but found nothing new, it tells you once a day so you know it's alive

No dashboard. No browser tab. Just a Telegram message when something worth applying to shows up.

---

## Stack

| Layer | Service | Cost |
|---|---|---|
| Scheduler | AWS EventBridge | Free |
| Runtime | AWS Lambda — Python 3.12 | Free (1M req/month) |
| Job listings | JSearch API via RapidAPI | Free (200 req/month) |
| AI filtering | Groq — LLaMA 3.1 8B Instant | Free |
| Deduplication | AWS DynamoDB | Free (25 GB) |
| Notifications | Telegram Bot API | Free forever |

**Total: $0/month.** Everything fits in AWS + Groq free tiers.

---

## Project structure

```
job-search-agent/
├── handler.py        # Lambda entry point — orchestrates the full flow
├── searcher.py       # JSearch API integration
├── filter.py         # Groq AI filtering against your profile
├── storage.py        # DynamoDB deduplication + daily heartbeat
├── notifier.py       # Telegram notifications
├── profile.json      # Your profile — source of truth for AI filtering
├── package.py        # Cross-platform packaging script
├── deploy.sh         # Full deploy: package → Lambda → EventBridge
├── requirements.txt
└── .env.example
```

---

## Setup

### Prerequisites

- Python 3.12+
- AWS CLI configured (`aws configure`)
- Git Bash (Windows) or any bash shell

### 1. Clone and configure

```bash
git clone https://github.com/Ossccaarrtz/JobHunting.git
cd JobHunting/job-search-agent
cp .env.example .env
```

Fill in `.env`:

```env
JSEARCH_API_KEY=        # RapidAPI → JSearch → Subscribe (free BASIC tier)
GROQ_API_KEY=           # console.groq.com → API Keys (free)
TELEGRAM_BOT_TOKEN=     # @BotFather on Telegram → /newbot
TELEGRAM_CHAT_ID=       # Your personal chat ID (see below)
DYNAMODB_TABLE=job-search-seen
AWS_REGION=us-east-1
```

**Getting your Telegram chat ID:**
1. Start a conversation with your bot on Telegram
2. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Copy the `id` value inside the `chat` object

### 2. Create AWS infrastructure (run once)

```bash
# DynamoDB table
aws dynamodb create-table \
  --table-name job-search-seen \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Enable TTL — auto-deletes records after 30 days
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

### 3. Deploy

```bash
bash deploy.sh
```

This packages dependencies, creates (or updates) the Lambda function, sets all environment variables, and creates the EventBridge schedule. One command, done.

### 4. Test manually

```bash
# Invoke the Lambda directly
aws lambda invoke \
  --function-name job-search-agent \
  --region us-east-1 \
  response.json && type response.json   # Windows
  # cat response.json                   # Mac/Linux

# Tail logs
aws logs tail /aws/lambda/job-search-agent --region us-east-1
```

Expected output: `{"procesados": N, "notificados": M}`

---

## Customizing your profile

Edit `profile.json` to match your actual CV. The AI uses these fields to decide if a job is worth sending you:

```json
{
  "rol_buscado": {
    "titulos": ["Software Engineer Intern", "Backend Engineer Intern"],
    "ubicacion_preferida": ["Remote", "USA"]
  },
  "skills": {
    "backend": ["FastAPI", "Flask", "Node.js"],
    "cloud": ["AWS Lambda", "DynamoDB"]
  },
  "criterios_match_ia": {
    "must_have": ["internship or new grad role", "no sponsorship required"],
    "nice_to_have": ["remote", "Python or JavaScript stack"],
    "dealbreakers": ["requires visa sponsorship", "2+ years experience required"]
  }
}
```

To add more search queries, edit `QUERIES` in `searcher.py`. Stay within the JSearch free tier:

```
2 queries × 3 runs/day × 30 days = 180 req/month  ✅  (limit: 200)
```

### Redeploy after any changes

```bash
bash deploy.sh
```

---

## How the AI filtering works

Each job description gets evaluated by LLaMA 3.1 against your profile in a single prompt:

```
Does this job match a candidate with [your skills], [your citizenship], looking for [your target roles]?
Consider must_have requirements and dealbreakers.
Respond only with JSON: {"match": true/false, "razon": "reason in max 20 words"}
```

Jobs that error during AI evaluation are skipped and retried next run — they don't get marked as seen in DynamoDB.

---

## AWS cost breakdown

| Service | Usage | Cost |
|---|---|---|
| Lambda | ~90 invocations/month × ~30s each | $0 — well within free tier |
| EventBridge | 1 rule, 90 triggers/month | $0 |
| DynamoDB | ~180 writes + ~180 reads/month | $0 — on-demand, negligible |
| CloudWatch Logs | minimal log volume | $0 |

The Lambda will run for years before you pay a cent.

---

## License

MIT
