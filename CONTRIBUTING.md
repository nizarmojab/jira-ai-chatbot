# Contributing

Thanks for your interest in improving this project.

## How To Contribute

1. Fork the repository
2. Create a feature branch
3. Make focused changes
4. Test locally
5. Open a pull request with a clear description

## Local Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Then configure your Jira and OpenAI credentials locally.

## Recommended Contribution Areas

- chatbot accuracy and tool orchestration
- Jira API robustness and error handling
- web UI polish
- dashboard improvements
- documentation
- automated tests
- encoding cleanup in user-facing files

## Pull Request Guidelines

- Keep changes focused and easy to review
- Update documentation when behavior changes
- Do not commit secrets or local environment files
- Prefer small, readable commits

## Security

Do not include:

- `.env`
- API keys
- Jira tokens
- personal account identifiers unless clearly intended and documented
