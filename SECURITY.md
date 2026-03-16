# Security

- Do not commit `.env`, credential files, or captured responses containing secrets.
- Use `.env.example` as a template only.
- Error handling in both clients must avoid printing API keys.
- Treat live API verification as opt-in and run it only in trusted environments.
