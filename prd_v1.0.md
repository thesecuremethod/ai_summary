

# AI Research Agent – PRD v1.0

## Objective
Build an agent that collects, summarizes, and delivers daily updates about new AI research (papers, videos, articles) using cloud infrastructure.

## v1 Scope
- Data sources: arXiv, YouTube, Feedly
- Summarization: GPT-4 via OpenAI API
- Infrastructure: AWS (Lambda, DynamoDB, EventBridge, SES)
- Storage: DynamoDB (for state), optional S3 (for content)
- Delivery: daily email via AWS SES

## Non-Goals
- No real-time alerts
- No UI dashboard
- No local runtime

## Key Components
1. Data ingestors (Lambda)
2. Summarizer (GPT-4 API)
3. State tracker (DynamoDB)
4. Scheduler (EventBridge)
5. Email sender (SES)

## Success Criteria
- Daily digest with top 5 summarized items
- Summaries are accurate and relevant
- No duplicate content across days

## Risks
- API limits or costs (OpenAI, AWS)
- Content parsing failures
- LLM summary drift

## Future Ideas
- Bedrock as LLM provider
- Telegram/mobile delivery
- Feedback loop for personalization
